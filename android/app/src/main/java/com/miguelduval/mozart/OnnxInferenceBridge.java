package com.miguelduval.mozart;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
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
    private static final int CHANNEL_BASE = 16;
    private static final int NOTE_BASE = 32;
    private static final int VELOCITY_BASE = 160;
    private static final int TIME_SHIFT_BASE = 192;
    private static final int DURATION_BASE = 256;
    private static final int CONTROLLER_BASE = 352;
    private static final int CONTROL_VALUE_BASE = 480;
    private static final String INPUT_IDS = "input_ids";
    private static final String[] CONDITIONING_INPUT_NAMES = {
            "style_id",
            "substyle_id",
            "mood_id",
            "rhythm_id",
            "role_id",
            "performance_controls"
    };

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

            final Map<String, Object> conditioningInputs =
                    parseConditioningRequest(requestJson);

            final Class<?> envClass =
                    Class.forName("ai.onnxruntime.OrtEnvironment");
            final Class<?> tensorClass =
                    Class.forName("ai.onnxruntime.OnnxTensor");
            final Object environment =
                    envClass.getMethod("getEnvironment").invoke(null);

            final Map<String, Object> conditioningTensors =
                    new LinkedHashMap<>();
            try {
                for (String inputName : CONDITIONING_INPUT_NAMES) {
                    final Object values = conditioningInputs.get(inputName);
                    if (values instanceof long[]) {
                        final long[] conditionValues = (long[]) values;
                        final LongBuffer conditionBuffer =
                                ByteBuffer.allocateDirect(
                                                conditionValues.length * Long.BYTES)
                                        .order(ByteOrder.nativeOrder())
                                        .asLongBuffer();
                        conditionBuffer.put(conditionValues);
                        conditionBuffer.rewind();
                        conditioningTensors.put(
                                inputName,
                                createLongTensor(
                                        tensorClass,
                                        environment,
                                        conditionBuffer,
                                        new long[] {1}));
                    } else if (values instanceof float[]) {
                        final float[] conditionValues = (float[]) values;
                        final FloatBuffer conditionBuffer =
                                ByteBuffer.allocateDirect(
                                                conditionValues.length * Float.BYTES)
                                        .order(ByteOrder.nativeOrder())
                                        .asFloatBuffer();
                        conditionBuffer.put(conditionValues);
                        conditionBuffer.rewind();
                        conditioningTensors.put(
                                inputName,
                                createFloatTensor(
                                        tensorClass,
                                        environment,
                                        conditionBuffer,
                                        new long[] {1, 5}));
                    } else {
                        throw new IllegalArgumentException(
                                "unsupported ONNX conditioning input: "
                                        + inputName);
                    }
                }

                final Object session =
                        envClass.getMethod("createSession", String.class)
                                .invoke(environment, artifact.getAbsolutePath());

                try {
                    validateSessionAbi(session, root);

                    final List<Integer> tokens = new ArrayList<>();
                    tokens.add(runtime.getInt("bos_token_id"));

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
                        inputs.putAll(conditioningTensors);

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
                        final int next = argmaxAllowedNextToken(
                                logits,
                                tokens,
                                runtime.getInt("bos_token_id"),
                                runtime.getInt("eos_token_id"));
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
            } finally {
                for (Object tensor : conditioningTensors.values()) {
                    closeQuietly(tensor);
                }
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

        validateCanonicalConditioningOrder(runtime);

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

    private static void validateCanonicalConditioningOrder(
            JSONObject runtime) throws Exception {
        final JSONArray conditioningInputNames =
                runtime.optJSONArray("conditioning_input_names");
        if (conditioningInputNames == null ||
                conditioningInputNames.length() !=
                        CONDITIONING_INPUT_NAMES.length) {
            throw new IllegalArgumentException(
                    "manifest.runtime.conditioning_input_names must declare all conditioning inputs");
        }

        for (int i = 0; i < CONDITIONING_INPUT_NAMES.length; ++i) {
            if (!CONDITIONING_INPUT_NAMES[i].equals(
                    conditioningInputNames.getString(i))) {
                throw new IllegalArgumentException(
                        "manifest.runtime.conditioning_input_names must match canonical order");
            }
        }

        final String[] performanceControlNames = {
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation"
        };
        final JSONArray configuredPerformanceControls =
                runtime.optJSONArray("performance_control_names");
        if (configuredPerformanceControls == null ||
                configuredPerformanceControls.length() !=
                        performanceControlNames.length) {
            throw new IllegalArgumentException(
                    "manifest.runtime.performance_control_names must declare all performance controls");
        }

        for (int i = 0; i < performanceControlNames.length; ++i) {
            if (!performanceControlNames[i].equals(
                    configuredPerformanceControls.getString(i))) {
                throw new IllegalArgumentException(
                        "manifest.runtime.performance_control_names must match canonical order");
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void validateSessionAbi(
            Object session,
            JSONObject root) throws Exception {
        final JSONObject runtime = root.getJSONObject("runtime");
        final String inputName = runtime.getString("input_name");
        final String outputName = runtime.getString("output_name");
        validateCanonicalConditioningOrder(runtime);
        if (!INPUT_IDS.equals(inputName) || !"logits".equals(outputName)) {
            throw new IllegalArgumentException(
                    "experimental Mozart ONNX ABI requires input_ids -> logits");
        }

        final JSONArray manifestInputs = root.getJSONArray("inputs");
        if (manifestInputs.length() != 1 + CONDITIONING_INPUT_NAMES.length) {
            throw new IllegalArgumentException(
                    "experimental Mozart ONNX ABI requires exactly 7 inputs");
        }

        final Map<String, ?> inputInfo =
                (Map<String, ?>) session.getClass()
                        .getMethod("getInputInfo")
                        .invoke(session);
        final Map<String, ?> outputInfo =
                (Map<String, ?>) session.getClass()
                        .getMethod("getOutputInfo")
                        .invoke(session);

        final Object inputNode = inputInfo.get(inputName);
        final Object outputNode = outputInfo.get(outputName);
        if (inputNode == null) {
            throw new IllegalArgumentException(
                    "ONNX input tensor not found: " + inputName);
        }
        if (outputNode == null) {
            throw new IllegalArgumentException(
                    "ONNX output tensor not found: " + outputName);
        }

        final JSONObject tokenTensor =
                findManifestTensor(manifestInputs, INPUT_IDS);
        if (!"int64".equalsIgnoreCase(
                normalizeOrtType(tokenTensor.getString("dtype")))) {
            throw new IllegalArgumentException(
                    "ONNX manifest input_ids must be int64");
        }
        if (tokenTensor.getJSONArray("shape").length() != 2) {
            throw new IllegalArgumentException(
                    "ONNX manifest input_ids must have rank 2");
        }
        validateSessionTensor(inputNode, tokenTensor, "input input_ids");

        final String[] conditionDtypes = {
                "int64",
                "int64",
                "int64",
                "int64",
                "int64",
                "float32"
        };
        final int[] conditionRanks = {1, 1, 1, 1, 1, 2};

        for (int i = 0; i < CONDITIONING_INPUT_NAMES.length; ++i) {
            final String conditionName = CONDITIONING_INPUT_NAMES[i];
            final JSONObject tensor =
                    findManifestTensor(manifestInputs, conditionName);
            final String expectedDtype = conditionDtypes[i];
            final int expectedRank = conditionRanks[i];

            if (!expectedDtype.equalsIgnoreCase(
                    normalizeOrtType(tensor.getString("dtype")))) {
                throw new IllegalArgumentException(
                        "ONNX manifest " + conditionName
                                + " must be " + expectedDtype);
            }

            final JSONArray expectedShape = tensor.getJSONArray("shape");
            if (expectedShape.length() != expectedRank) {
                throw new IllegalArgumentException(
                        "ONNX manifest " + conditionName
                                + " rank mismatch");
            }
            if (expectedRank == 1 && expectedShape.getLong(0) != 1L) {
                throw new IllegalArgumentException(
                        "ONNX manifest " + conditionName
                                + " must have shape [1]");
            }
            if (expectedRank == 2 &&
                    (expectedShape.getLong(0) != 1L ||
                            expectedShape.getLong(1) != 5L)) {
                throw new IllegalArgumentException(
                        "ONNX manifest performance_controls must have shape [1,5]");
            }

            final Object node = inputInfo.get(conditionName);
            if (node == null) {
                throw new IllegalArgumentException(
                        "ONNX input tensor not found: " + conditionName);
            }
            validateSessionTensor(
                    node,
                    tensor,
                    "input " + conditionName);
        }

        validateSessionTensor(
                outputNode,
                findManifestTensor(root.getJSONArray("outputs"), outputName),
                "output logits");

        if (!"int64".equalsIgnoreCase(runtime.getString("input_dtype"))) {
            throw new IllegalArgumentException(
                    "ONNX runtime input_dtype is not int64");
        }
    }

    private static JSONObject findManifestTensor(
            JSONArray tensors,
            String name) throws Exception {
        for (int i = 0; i < tensors.length(); ++i) {
            final JSONObject tensor = tensors.getJSONObject(i);
            if (name.equals(tensor.optString("name", ""))) {
                return tensor;
            }
        }
        throw new IllegalArgumentException(
                "manifest tensor is missing: " + name);
    }

    private static void validateSessionTensor(
            Object nodeInfo,
            JSONObject manifestTensor,
            String role) throws Exception {
        final Object valueInfo =
                nodeInfo.getClass()
                        .getMethod("getInfo")
                        .invoke(nodeInfo);

        final String actualType =
                normalizeOrtType(
                        String.valueOf(
                                valueInfo.getClass()
                                        .getMethod("getType")
                                        .invoke(valueInfo)));
        final String expectedType =
                normalizeOrtType(manifestTensor.getString("dtype"));

        if (!expectedType.equalsIgnoreCase(actualType)) {
            throw new IllegalArgumentException(
                    "ONNX " + role + " dtype mismatch: expected "
                            + expectedType + " actual " + actualType);
        }

        final Object actualShape =
                valueInfo.getClass()
                        .getMethod("getShape")
                        .invoke(valueInfo);
        final JSONArray expectedShape =
                manifestTensor.getJSONArray("shape");

        if (actualShape == null || !actualShape.getClass().isArray()) {
            throw new IllegalArgumentException(
                    "ONNX " + role + " shape is unavailable");
        }

        final int actualRank = java.lang.reflect.Array.getLength(actualShape);
        if (actualRank != expectedShape.length()) {
            throw new IllegalArgumentException(
                    "ONNX " + role + " rank mismatch");
        }

        for (int i = 0; i < actualRank; ++i) {
            final long actualDimension =
                    java.lang.reflect.Array.getLong(actualShape, i);
            final long expectedDimension =
                    expectedShape.getLong(i);

            // Negative dimensions represent dynamic/unknown extents in the
            // Mozart manifest and therefore match any runtime dimension.
            if (expectedDimension >= 0 &&
                    actualDimension != expectedDimension) {
                throw new IllegalArgumentException(
                        "ONNX " + role + " shape mismatch at dimension "
                                + i + ": expected "
                                + expectedDimension + " actual "
                                + actualDimension);
            }
        }
    }

    private static String normalizeOrtType(String type) {
        String normalized = type == null ? "" : type.trim().toLowerCase();
        if (normalized.startsWith("tensor(") &&
                normalized.endsWith(")")) {
            normalized = normalized.substring(7, normalized.length() - 1);
        }
        if ("float".equals(normalized)) {
            return "float32";
        }
        return normalized;
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

    private static Map<String, Object> parseConditioningRequest(
            String requestJson) throws Exception {
        final JSONObject request =
                new JSONObject(requestJson == null || requestJson.isEmpty()
                        ? "{}"
                        : requestJson);

        final String[] requestNames = {
                "style",
                "substyle",
                "mood",
                "rhythm",
                "role"
        };
        final int[] maximums = {5, 6, 7, 6, 7};
        final Map<String, Object> result = new LinkedHashMap<>();

        for (int i = 0; i < requestNames.length; ++i) {
            final String requestName = requestNames[i];
            final Object raw = request.get(requestName);
            if (!(raw instanceof Number)) {
                throw new IllegalArgumentException(
                        "ONNX request field " + requestName
                                + " must be an integer");
            }
            final double value = ((Number) raw).doubleValue();
            if (!Double.isFinite(value) ||
                    Math.rint(value) != value ||
                    value < 0.0 ||
                    value > maximums[i]) {
                throw new IllegalArgumentException(
                        "ONNX request field " + requestName
                                + " is outside its vocabulary range");
            }
            result.put(
                    CONDITIONING_INPUT_NAMES[i],
                    new long[] {((Number) raw).longValue()});
        }

        final String[] controlNames = {
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation"
        };
        final float[] controls = new float[controlNames.length];
        for (int i = 0; i < controlNames.length; ++i) {
            final String name = controlNames[i];
            final Object raw = request.get(name);
            if (!(raw instanceof Number)) {
                throw new IllegalArgumentException(
                        "ONNX request field " + name
                                + " must be a number");
            }
            final double value = ((Number) raw).doubleValue();
            if (!Double.isFinite(value) || value < 0.0 || value > 1.0) {
                throw new IllegalArgumentException(
                        "ONNX request field " + name
                                + " must be in [0, 1]");
            }
            controls[i] = (float) value;
        }
        result.put("performance_controls", controls);

        return result;
    }

    private static Object createFloatTensor(
            Class<?> tensorClass,
            Object environment,
            FloatBuffer buffer,
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
                "OnnxTensor.createTensor(environment, FloatBuffer, shape)");
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

    private static int argmaxAllowedNextToken(
            double[] values,
            List<Integer> tokens,
            int bosToken,
            int eosToken) {
        if (values == null || values.length != MOZART_VOCABULARY_SIZE) {
            return argmax(values);
        }
        if (tokens == null || tokens.isEmpty()) {
            throw new IllegalArgumentException("token history must not be empty");
        }

        int bestIndex = -1;
        double bestValue = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < MOZART_VOCABULARY_SIZE; ++i) {
            if (!isAllowedNextToken(tokens, i, bosToken, eosToken)) {
                continue;
            }
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
                    "ONNX logits contain no grammar-valid next token");
        }
        return bestIndex;
    }

    private static boolean isAllowedNextToken(
            List<Integer> tokens,
            int nextToken,
            int bosToken,
            int eosToken) {
        if (tokens == null || tokens.isEmpty() ||
                nextToken < 0 || nextToken >= MOZART_VOCABULARY_SIZE) {
            return false;
        }

        final int last = tokens.get(tokens.size() - 1);
        if (last == bosToken) {
            return isChannelToken(nextToken) || isTimeShiftToken(nextToken);
        }
        if (isNoteToken(last)) {
            return isVelocityToken(nextToken);
        }
        if (isVelocityToken(last)) {
            return isDurationToken(nextToken);
        }
        if (isControllerToken(last)) {
            return isControlValueToken(nextToken);
        }
        if (isDurationToken(last) || isControlValueToken(last)) {
            return nextToken == eosToken ||
                    isChannelToken(nextToken) ||
                    isTimeShiftToken(nextToken) ||
                    isNoteToken(nextToken) ||
                    isControllerToken(nextToken);
        }
        if (isTimeShiftToken(last)) {
            return isChannelToken(nextToken) ||
                    isTimeShiftToken(nextToken) ||
                    (hasChannelToken(tokens) &&
                            (isNoteToken(nextToken) ||
                                    isControllerToken(nextToken)));
        }
        if (isChannelToken(last)) {
            return isNoteToken(nextToken) || isControllerToken(nextToken);
        }
        if (last == eosToken) {
            return false;
        }
        return false;
    }

    private static boolean hasChannelToken(List<Integer> tokens) {
        for (Integer value : tokens) {
            if (value != null && isChannelToken(value)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isChannelToken(int token) {
        return token >= 16 && token < 32;
    }

    private static boolean isNoteToken(int token) {
        return token >= 32 && token < 160;
    }

    private static boolean isVelocityToken(int token) {
        return token >= 160 && token < 192;
    }

    private static boolean isTimeShiftToken(int token) {
        return token >= 192 && token < 256;
    }

    private static boolean isDurationToken(int token) {
        return token >= 256 && token < 352;
    }

    private static boolean isControllerToken(int token) {
        return token >= 352 && token < 480;
    }

    private static boolean isControlValueToken(int token) {
        return token >= 480 && token < MOZART_VOCABULARY_SIZE;
    }

    private static int argmax(double[] values) {
        if (values == null || values.length == 0) {
            throw new IllegalArgumentException("empty ONNX logits");
        }

        if (values.length != MOZART_VOCABULARY_SIZE) {
            throw new IllegalArgumentException(
                    "ONNX logits vocabulary size must 512");
        }

        int bestIndex = -1;
        double bestValue = Double.NEGATIVE_INFINITY;
        final int limit = MOZART_VOCABULARY_SIZE;

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
