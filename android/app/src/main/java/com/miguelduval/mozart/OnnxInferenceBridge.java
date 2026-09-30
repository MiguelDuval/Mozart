package com.miguelduval.mozart;

import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.LongBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class OnnxInferenceBridge {
    private static final String TAG = "MozartOnnx";
    private static final int MOZART_VOCABULARY_SIZE = 512;
    private static final int BOS = 1;
    private static final int EOS = 2;

    private OnnxInferenceBridge() {}

    public static boolean isRuntimeAvailable() {
        try {
            Class.forName("ai.onnxruntime.OrtEnvironment");
            Class.forName("ai.onnxruntime.OnnxTensor");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    public static String generate(
            String artifactPath,
            String manifestPath,
            String requestJson,
            int requestedMaxTokens) {
        final long started = System.nanoTime();

        try {
            if (artifactPath == null || artifactPath.isEmpty()) {
                return response("UNAVAILABLE", 0, 0,
                        "", "ONNX model artifact path is missing");
            }
            if (manifestPath == null || manifestPath.isEmpty()) {
                return response("UNAVAILABLE", 0, 0,
                        "", "ONNX model manifest path is missing");
            }

            final File artifact = new File(artifactPath);
            final File manifest = new File(manifestPath);
            if (!artifact.isFile()) {
                return response("UNAVAILABLE", 0, elapsedMs(started),
                        "", "ONNX model artifact is missing");
            }
            if (!manifest.isFile()) {
                return response("UNAVAILABLE", 0, elapsedMs(started),
                        "", "ONNX model manifest is missing");
            }

            final JSONObject root = new JSONObject(readUtf8(manifest));
            validateManifest(root, artifact);

            if (!isRuntimeAvailable()) {
                return response("UNAVAILABLE", 0, elapsedMs(started),
                        "", "ONNX Runtime is not present in this build");
            }

            final JSONObject runtime = root.getJSONObject("runtime");
            final int contextLength =
                    runtime.getInt("context_length_tokens");
            final int configuredMax =
                    runtime.getInt("max_generated_tokens");
            final int maxTokens = Math.min(
                    Math.max(2, requestedMaxTokens),
                    configuredMax);

            if (maxTokens < 2) {
                return response("FAILED", 0, elapsedMs(started),
                        "", "ONNX maximum generation length is invalid");
            }

            // The request is forwarded so a later model-specific encoder can
            // use the same bridge without changing the native service boundary.
            if (requestJson == null || requestJson.isEmpty()) {
                requestJson = "{}";
            }

            final Class<?> envClass =
                    Class.forName("ai.onnxruntime.OrtEnvironment");
            final Class<?> tensorClass =
                    Class.forName("ai.onnxruntime.OnnxTensor");
            final Object environment =
                    envClass.getMethod("getEnvironment").invoke(null);

            final Object session =
                    envClass.getMethod("createSession", String.class)
                            .invoke(environment, artifact.getAbsolutePath());

            final List<Integer> tokens = new ArrayList<>();
            tokens.add(runtime.getInt("bos_token_id"));

            try {
                for (int step = 0; step < maxTokens - 1; ++step) {
                    if (tokens.size() >= contextLength) {
                        return response(
                                "FAILED",
                                0,
                                elapsedMs(started),
                                encodeTokens(tokens),
                                "ONNX context exhausted before EOS");
                    }

                    final long[] inputValues = new long[tokens.size()];
                    for (int i = 0; i < tokens.size(); ++i) {
                        inputValues[i] = tokens.get(i);
                    }

                    final LongBuffer inputBuffer =
                            ByteBuffer.allocateDirect(
                                            inputValues.length * Long.BYTES)
                                    .order(ByteOrder.nativeOrder())
                                    .asLongBuffer();
                    inputBuffer.put(inputValues);
                    inputBuffer.rewind();

                    final Object inputTensor =
                            createLongTensor(
                                    tensorClass,
                                    environment,
                                    inputBuffer,
                                    new long[] {1, inputValues.length});

                    final Map<String, Object> inputs = new LinkedHashMap<>();
                    inputs.put(runtime.getString("input_name"), inputTensor);

                    Object sessionResult = null;
                    Object outputValue = null;
                    try {
                        final Method runMethod =
                                session.getClass().getMethod("run", Map.class);
                        sessionResult = runMethod.invoke(session, inputs);
                        outputValue = getResultValue(
                                sessionResult,
                                runtime.getString("output_name"));
                        if (outputValue == null) {
                            throw new IllegalArgumentException(
                                    "ONNX output tensor was not found");
                        }
                        final Object raw = outputValue.getClass()
                                .getMethod("getValue")
                                .invoke(outputValue);

                        final double[] logits = extractLastLogits(raw);
                        final int next = argmax(logits);
                        if (next < 0 || next >= MOZART_VOCABULARY_SIZE) {
                            return response(
                                    "FAILED",
                                    0,
                                    elapsedMs(started),
                                    encodeTokens(tokens),
                                    "ONNX output token is outside Mozart vocabulary");
                        }

                        tokens.add(next);
                        if (next == runtime.getInt("eos_token_id")) {
                            return response(
                                    "OK",
                                    0,
                                    elapsedMs(started),
                                    encodeTokens(tokens),
                                    "");
                        }
                    } finally {
                        closeQuietly(outputValue);
                        closeQuietly(sessionResult);
                        closeQuietly(inputTensor);
                    }
                }

                return response(
                        "FAILED",
                        0,
                        elapsedMs(started),
                        encodeTokens(tokens),
                        "ONNX model did not emit EOS before max_generated_tokens");
            } finally {
                closeQuietly(session);
            }
        } catch (ClassNotFoundException e) {
            return response(
                    "UNAVAILABLE",
                    0,
                    elapsedMs(started),
                    "",
                    "ONNX Runtime is not present in this build");
        } catch (Throwable e) {
            Log.w(TAG, "ONNX generation failed", e);
            final String message = e.getMessage() == null
                    ? e.getClass().getSimpleName()
                    : e.getMessage();
            return response(
                    "FAILED",
                    0,
                    elapsedMs(started),
                    "",
                    sanitize(message));
        }
    }

    private static void validateManifest(
            JSONObject root,
            File artifact) throws Exception {
        if (root.optInt("manifest_schema_version", -1) != 1) {
            throw new IllegalArgumentException(
                    "unsupported model manifest schema");
        }

        final String format = root.optString("model_format", "");
        if (!"onnx".equalsIgnoreCase(format)) {
            throw new IllegalArgumentException(
                    "manifest model_format must be onnx");
        }

        final String vocabulary =
                root.optString("vocabulary_id", "");
        final int vocabularySize =
                root.optInt("vocabulary_size", -1);
        if (!"mozart-midi-events-v1".equals(vocabulary) ||
                vocabularySize != MOZART_VOCABULARY_SIZE) {
            throw new IllegalArgumentException(
                    "manifest does not match Mozart 512-token ABI");
        }

        final String modelHash =
                root.optString("model_sha256", "").trim();
        final String distribution =
                root.optString("distribution_class", "").trim();
        final JSONObject runtime =
                root.optJSONObject("runtime");
        if (runtime == null) {
            throw new IllegalArgumentException(
                    "manifest.runtime is required by the experimental ONNX adapter");
        }

        if (!"onnxruntime".equalsIgnoreCase(
                runtime.optString("backend", ""))) {
            throw new IllegalArgumentException(
                    "manifest.runtime.backend must be onnxruntime");
        }

        if (!"mozart_ids".equalsIgnoreCase(
                runtime.optString("token_mode", "")) ||
                runtime.optInt(
                        "external_vocabulary_size", -1) !=
                        MOZART_VOCABULARY_SIZE) {
            throw new IllegalArgumentException(
                    "external model vocabulary requires a Mozart token adapter");
        }

        if (!"int64".equalsIgnoreCase(
                runtime.optString("input_dtype", ""))) {
            throw new IllegalArgumentException(
                    "first ONNX adapter requires int64 input_ids");
        }

        final String inputName =
                runtime.optString("input_name", "");
        final String outputName =
                runtime.optString("output_name", "");
        final int contextLength =
                runtime.optInt("context_length_tokens", 0);
        final int maxGenerated =
                runtime.optInt("max_generated_tokens", 0);
        final int bos =
                runtime.optInt("bos_token_id", BOS);
        final int eos =
                runtime.optInt("eos_token_id", EOS);

        if (inputName.isEmpty() || outputName.isEmpty()) {
            throw new IllegalArgumentException(
                    "manifest runtime input/output names are required");
        }
        if (contextLength < 2 || maxGenerated < 2) {
            throw new IllegalArgumentException(
                    "manifest context/generation lengths are invalid");
        }
        if (bos != BOS || eos != EOS) {
            throw new IllegalArgumentException(
                    "manifest BOS/EOS must match Mozart BOS=1 and EOS=2");
        }

        if (modelHash.equals("<FROZEN>") || modelHash.isEmpty()) {
            final boolean allowUnhashed =
                    "private_experimental".equals(distribution) &&
                    runtime.optBoolean("allow_unhashed_experimental", false);
            if (!allowUnhashed) {
                throw new IllegalArgumentException(
                        "experimental model requires a concrete model_sha256");
            }
        } else {
            final String actual = sha256(artifact);
            if (!modelHash.equalsIgnoreCase(actual)) {
                throw new IllegalArgumentException(
                        "model_sha256 does not match artifact");
            }
        }
    }

    private static Object createLongTensor(
            Class<?> tensorClass,
            Object environment,
            LongBuffer buffer,
            long[] shape) throws Exception {
        for (Method method : tensorClass.getMethods()) {
            if (!"createTensor".equals(method.getName())) {
                continue;
            }

            final Class<?>[] parameters = method.getParameterTypes();
            if (parameters.length != 3 ||
                    !parameters[0].isAssignableFrom(environment.getClass()) ||
                    !parameters[1].isAssignableFrom(buffer.getClass()) ||
                    parameters[2] != long[].class) {
                continue;
            }

            return method.invoke(
                    null,
                    environment,
                    buffer,
                    shape);
        }

        throw new NoSuchMethodException(
                "OnnxTensor.createTensor(environment, LongBuffer, shape)");
    }

    private static Object getResultValue(
            Object sessionResult,
            String outputName) throws Exception {
        try {
            final Method byName =
                    sessionResult.getClass().getMethod("get", String.class);
            final Object result = byName.invoke(sessionResult, outputName);
            if (result instanceof java.util.Optional) {
                final java.util.Optional<?> optional =
                        (java.util.Optional<?>) result;
                if (optional.isPresent()) {
                    return optional.get();
                }
                return null;
            }
            if (result != null) {
                return result;
            }
        } catch (NoSuchMethodException ignored) {
            // Older API fallback.
        }

        final Method byIndex =
                sessionResult.getClass().getMethod("get", int.class);
        return byIndex.invoke(sessionResult, 0);
    }

    private static double[] extractLastLogits(Object value) {
        if (value instanceof float[][][]) {
            final float[][][] array = (float[][][]) value;
            if (array.length == 0 || array[0].length == 0) {
                throw new IllegalArgumentException("empty ONNX logits");
            }
            return toDouble(array[0][array[0].length - 1]);
        }
        if (value instanceof double[][][]) {
            final double[][][] array = (double[][][]) value;
            if (array.length == 0 || array[0].length == 0) {
                throw new IllegalArgumentException("empty ONNX logits");
            }
            return array[0][array[0].length - 1];
        }
        if (value instanceof float[][]) {
            final float[][] array = (float[][]) value;
            if (array.length == 0) {
                throw new IllegalArgumentException("empty ONNX logits");
            }
            return toDouble(array[array.length - 1]);
        }
        if (value instanceof double[][]) {
            final double[][] array = (double[][]) value;
            if (array.length == 0) {
                throw new IllegalArgumentException("empty ONNX logits");
            }
            return array[array.length - 1];
        }
        if (value instanceof float[]) {
            return toDouble((float[]) value);
        }
        if (value instanceof double[]) {
            return (double[]) value;
        }

        throw new IllegalArgumentException(
                "unsupported ONNX output type "
                        + value.getClass().getName());
    }

    private static double[] toDouble(float[] source) {
        final double[] result = new double[source.length];
        for (int i = 0; i < source.length; ++i) {
            result[i] = source[i];
        }
        return result;
    }

    private static int argmax(double[] values) {
        if (values == null || values.length == 0) {
            throw new IllegalArgumentException("empty ONNX logits");
        }

        int bestIndex = -1;
        double bestValue = Double.NEGATIVE_INFINITY;
        final int limit = Math.min(values.length, MOZART_VOCABULARY_SIZE);

        for (int i = 0; i < limit; ++i) {
            final double value = values[i];
            if (Double.isNaN(value)) {
                continue;
            }
            if (bestIndex < 0 || value > bestValue) {
                bestIndex = i;
                bestValue = value;
            }
        }

        if (bestIndex < 0) {
            throw new IllegalArgumentException(
                    "ONNX logits contain no usable value");
        }

        return bestIndex;
    }

    private static String encodeTokens(List<Integer> tokens) {
        final StringBuilder result = new StringBuilder();
        for (int i = 0; i < tokens.size(); ++i) {
            if (i > 0) {
                result.append(',');
            }
            result.append(tokens.get(i));
        }
        return result.toString();
    }

    private static String response(
            String status,
            long confidenceMicro,
            long generationMs,
            String tokens,
            String message) {
        return status + "|"
                + confidenceMicro + "|"
                + generationMs + "|"
                + tokens + "|"
                + sanitize(message);
    }

    private static String readUtf8(File file) throws Exception {
        final StringBuilder result = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        new FileInputStream(file),
                        StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                result.append(line).append('\n');
            }
        }
        return result.toString();
    }

    private static String sha256(File file) throws Exception {
        final MessageDigest digest = MessageDigest.getInstance("SHA-256");
        final byte[] buffer = new byte[8192];
        try (FileInputStream input = new FileInputStream(file)) {
            int count;
            while ((count = input.read(buffer)) != -1) {
                digest.update(buffer, 0, count);
            }
        }

        final StringBuilder hex = new StringBuilder(64);
        for (byte value : digest.digest()) {
            hex.append(String.format("%02x", value & 0xFF));
        }
        return hex.toString();
    }

    private static long elapsedMs(long started) {
        return (System.nanoTime() - started) / 1_000_000L;
    }

    private static String sanitize(String message) {
        if (message == null) {
            return "";
        }
        return message.replace('|', '/').replace('\n', ' ');
    }

    private static void closeQuietly(Object value) {
        if (!(value instanceof AutoCloseable)) {
            return;
        }

        try {
            ((AutoCloseable) value).close();
        } catch (Exception ignored) {
            // Best-effort cleanup for experimental inference.
        }
    }
}
