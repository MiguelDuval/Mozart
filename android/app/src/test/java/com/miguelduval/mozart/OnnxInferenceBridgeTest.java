package com.miguelduval.mozart;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.json.JSONArray;
import org.json.JSONObject;

import org.junit.Test;

public class OnnxInferenceBridgeTest {
    @Test
    public void argmaxRejectsNonMozartVocabularySizes() throws Exception {
        final Method method =
                OnnxInferenceBridge.class.getDeclaredMethod(
                        "argmax",
                        double[].class);
        method.setAccessible(true);

        try {
            method.invoke(null, new Object[] {new double[511]});
            org.junit.Assert.fail("expected vocabulary mismatch");
        } catch (java.lang.reflect.InvocationTargetException expected) {
            org.junit.Assert.assertTrue(
                    expected.getCause() instanceof IllegalArgumentException);
            org.junit.Assert.assertTrue(
                    expected.getCause().getMessage().contains(
                            "vocabulary size"));
        }

        try {
            method.invoke(null, new Object[] {new double[513]});
            org.junit.Assert.fail("expected vocabulary mismatch");
        } catch (java.lang.reflect.InvocationTargetException expected) {
            org.junit.Assert.assertTrue(
                    expected.getCause() instanceof IllegalArgumentException);
            org.junit.Assert.assertTrue(
                    expected.getCause().getMessage().contains(
                            "vocabulary size"));
        }
    }

    @Test
    public void grammarAllowsOnlyStructuralSuccessors() throws Exception {
        final Method method = findRequiredPrivateMethod(
                "isAllowedNextToken",
                List.class,
                int.class,
                int.class,
                int.class);

        final List<Integer> bos = List.of(1);
        assertTrue((Boolean) method.invoke(null, bos, 16, 1, 2));
        assertTrue((Boolean) method.invoke(null, bos, 192, 1, 2));
        assertFalse((Boolean) method.invoke(null, bos, 92, 1, 2));

        final List<Integer> channel = List.of(1, 16);
        assertTrue((Boolean) method.invoke(null, channel, 92, 1, 2));
        assertTrue((Boolean) method.invoke(null, channel, 352, 1, 2));
        assertFalse((Boolean) method.invoke(null, channel, 192, 1, 2));

        final List<Integer> note = List.of(1, 16, 92);
        assertTrue((Boolean) method.invoke(null, note, 160, 1, 2));
        assertFalse((Boolean) method.invoke(null, note, 256, 1, 2));
        assertFalse((Boolean) method.invoke(null, note, 352, 1, 2));

        final List<Integer> velocity = List.of(1, 16, 92, 160);
        assertTrue((Boolean) method.invoke(null, velocity, 256, 1, 2));
        assertFalse((Boolean) method.invoke(null, velocity, 160, 1, 2));

        final List<Integer> shifted = List.of(1, 16, 92, 160, 256, 207);
        assertTrue((Boolean) method.invoke(null, shifted, 92, 1, 2));
        assertTrue((Boolean) method.invoke(null, shifted, 352, 1, 2));
        assertTrue((Boolean) method.invoke(null, shifted, 192, 1, 2));

        final List<Integer> duration = List.of(1, 16, 92, 160, 256);
        assertTrue((Boolean) method.invoke(null, duration, 2, 1, 2));
        assertTrue((Boolean) method.invoke(null, duration, 16, 1, 2));
        assertTrue((Boolean) method.invoke(null, duration, 192, 1, 2));
        assertTrue((Boolean) method.invoke(null, duration, 92, 1, 2));
        assertTrue((Boolean) method.invoke(null, duration, 352, 1, 2));
        assertFalse((Boolean) method.invoke(null, duration, 160, 1, 2));

        final List<Integer> controller = List.of(1, 16, 352);
        assertTrue((Boolean) method.invoke(null, controller, 480, 1, 2));
        assertFalse((Boolean) method.invoke(null, controller, 256, 1, 2));

        final List<Integer> value = List.of(1, 16, 352, 480);
        assertTrue((Boolean) method.invoke(null, value, 2, 1, 2));
        assertTrue((Boolean) method.invoke(null, value, 192, 1, 2));
        assertTrue((Boolean) method.invoke(null, value, 92, 1, 2));
    }

    @Test
    public void grammarConstrainedArgmaxIgnoresHigherScoringInvalidTokens()
            throws Exception {
        final Method method = findRequiredPrivateMethod(
                "argmaxAllowedNextToken",
                double[].class,
                List.class,
                int.class,
                int.class);

        final double[] logits = new double[512];
        logits[92] = 1000.0;
        logits[161] = 12.0;
        logits[2] = 999.0;

        final Object result = method.invoke(
                null,
                logits,
                List.of(1, 16, 92),
                1,
                2);

        assertEquals(161, ((Integer) result).intValue());
    }

    @Test
    public void grammarRejectsTerminalContinuation() throws Exception {
        final Method method = findRequiredPrivateMethod(
                "isAllowedNextToken",
                List.class,
                int.class,
                int.class,
                int.class);

        final List<Integer> eos = new ArrayList<>();
        eos.add(1);
        eos.add(16);
        eos.add(92);
        eos.add(161);
        eos.add(256);
        eos.add(2);

        assertTrue(
                !(Boolean) method.invoke(null, eos, 92, 1, 2));
        assertTrue(
                !(Boolean) method.invoke(null, eos, 192, 1, 2));
    }

    @Test
    public void normalizeOrtTypeCanonicalizesOrtJavaTypes() throws Exception {
        final Method method =
                OnnxInferenceBridge.class.getDeclaredMethod(
                        "normalizeOrtType",
                        String.class);
        method.setAccessible(true);

        assertEquals("float32", method.invoke(null, "FLOAT"));
        assertEquals("int64", method.invoke(null, "INT64"));
        assertEquals("float32", method.invoke(null, "tensor(float)"));
        assertEquals("int64", method.invoke(null, "tensor(int64)"));
    }

    @Test
    public void conditioningRequestMapsAllSixConditioningTensors() throws Exception {
        final Method method = findRequiredPrivateMethod(
                "parseConditioningRequest",
                String.class);

        final Object raw = method.invoke(
                null,
                "{"
                        + "\"style\":3,"
                        + "\"substyle\":4,"
                        + "\"mood\":5,"
                        + "\"rhythm\":6,"
                        + "\"role\":7,"
                        + "\"density\":0.1,"
                        + "\"energy\":0.2,"
                        + "\"syncopation\":0.3,"
                        + "\"swing\":0.4,"
                        + "\"variation\":0.5"
                        + "}");
        assertTrue(raw instanceof Map);

        @SuppressWarnings("unchecked")
        final Map<String, Object> values = (Map<String, Object>) raw;
        assertEquals(6, values.size());
        assertArrayEquals(
                new long[] {3L},
                (long[]) values.get("style_id"));
        assertArrayEquals(
                new long[] {4L},
                (long[]) values.get("substyle_id"));
        assertArrayEquals(
                new long[] {5L},
                (long[]) values.get("mood_id"));
        assertArrayEquals(
                new long[] {6L},
                (long[]) values.get("rhythm_id"));
        assertArrayEquals(
                new long[] {7L},
                (long[]) values.get("role_id"));
        assertArrayEquals(
                new float[] {0.1F, 0.2F, 0.3F, 0.4F, 0.5F},
                (float[]) values.get("performance_controls"),
                1.0e-6F);
    }

    @Test
    public void floatTensorHelperCreatesFloat32TensorWithRequestedShape()
            throws Exception {
        final Method method = findRequiredPrivateMethod(
                "createFloatTensor",
                Class.class,
                Object.class,
                FloatBuffer.class,
                long[].class);

        final FloatBuffer source = FloatBuffer.allocate(5);
        source.put(new float[] {0.1F, 0.2F, 0.3F, 0.4F, 0.5F});
        source.rewind();

        final Object result = method.invoke(
                null,
                FakeTensorFactory.class,
                new FakeEnvironment(),
                source,
                new long[] {1L, 5L});

        assertTrue(result instanceof FakeTensor);
        final FakeTensor tensor = (FakeTensor) result;
        assertArrayEquals(
                new float[] {0.1F, 0.2F, 0.3F, 0.4F, 0.5F},
                tensor.values,
                1.0e-6F);
        assertArrayEquals(new long[] {1L, 5L}, tensor.shape);
    }

    @Test
    public void conditioningManifestOrderRejectsNonCanonicalLayout()
            throws Exception {
        final Method method = findRequiredPrivateMethod(
                "validateCanonicalConditioningOrder",
                JSONObject.class);

        final JSONObject runtime = new JSONObject();
        runtime.put(
                "conditioning_input_names",
                new JSONArray(
                        new String[] {
                                "style_id",
                                "substyle_id",
                                "mood_id",
                                "rhythm_id",
                                "role_id",
                                "performance_controls"
                        }));
        runtime.put(
                "performance_control_names",
                new JSONArray(
                        new String[] {
                                "density",
                                "energy",
                                "syncopation",
                                "swing",
                                "variation"
                        }));

        method.invoke(null, runtime);

        runtime.put(
                "performance_control_names",
                new String[] {
                        "density",
                        "energy",
                        "swing",
                        "syncopation",
                        "variation"
                });
        try {
            method.invoke(null, runtime);
            fail("expected non-canonical performance control order rejection");
        } catch (InvocationTargetException expected) {
            assertTrue(expected.getCause() instanceof IllegalArgumentException);
            assertTrue(
                    expected.getCause().getMessage().contains(
                            "performance_control_names"));
        }
    }

    @Test
    public void sessionAbiRejectsMissingConditioningInputs() throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateSessionAbi",
                Object.class,
                JSONObject.class);
        method.setAccessible(true);

        final FakeSession session = new FakeSession(false, false);
        try {
            method.invoke(null, session, conditioningManifest());
            fail("expected missing conditioning tensor rejection");
        } catch (InvocationTargetException expected) {
            assertTrue(expected.getCause() instanceof IllegalArgumentException);
            assertTrue(
                    expected.getCause().getMessage().contains("style_id"));
        }
    }

    @Test
    public void sessionAbiRejectsConditioningTensorContractMismatch()
            throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateSessionAbi",
                Object.class,
                JSONObject.class);
        method.setAccessible(true);

        final FakeSession session = new FakeSession(true, true);
        try {
            method.invoke(null, session, conditioningManifest());
            fail("expected conditioning tensor contract rejection");
        } catch (InvocationTargetException expected) {
            assertTrue(expected.getCause() instanceof IllegalArgumentException);
            assertTrue(
                    expected.getCause().getMessage().contains(
                            "performance_controls"));
        }
    }

    private static Method findRequiredPrivateMethod(
            String name,
            Class<?>... parameterTypes) throws Exception {
        try {
            final Method method =
                    OnnxInferenceBridge.class.getDeclaredMethod(
                            name,
                            parameterTypes);
            method.setAccessible(true);
            return method;
        } catch (NoSuchMethodException missing) {
            fail("expected OnnxInferenceBridge." + name
                    + " to exist before this test can pass");
            throw missing;
        }
    }

    private static JSONObject conditioningManifest() throws Exception {
        return new JSONObject(
                "{"
                        + "\"manifest_schema_version\":1,"
                        + "\"model_format\":\"onnx\","
                        + "\"vocabulary_id\":\"mozart-midi-events-v1\","
                        + "\"vocabulary_size\":512,"
                        + "\"inputs\":["
                        + "{\"name\":\"input_ids\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[-1,-1]},"
                        + "{\"name\":\"style_id\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[1]},"
                        + "{\"name\":\"substyle_id\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[1]},"
                        + "{\"name\":\"mood_id\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[1]},"
                        + "{\"name\":\"rhythm_id\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[1]},"
                        + "{\"name\":\"role_id\","
                        + "\"dtype\":\"int64\","
                        + "\"shape\":[1]},"
                        + "{\"name\":\"performance_controls\","
                        + "\"dtype\":\"float32\","
                        + "\"shape\":[1,5]}"
                        + "],"
                        + "\"outputs\":[{"
                        + "\"name\":\"logits\","
                        + "\"dtype\":\"float32\","
                        + "\"shape\":[-1,-1,512]}"
                        + "],"
                        + "\"runtime\":{"
                        + "\"input_name\":\"input_ids\","
                        + "\"output_name\":\"logits\","
                        + "\"input_dtype\":\"int64\","
                        + "\"conditioning_input_names\":["
                        + "\"style_id\",\"substyle_id\",\"mood_id\","
                        + "\"rhythm_id\",\"role_id\",\"performance_controls\""
                        + "],"
                        + "\"performance_control_names\":["
                        + "\"density\",\"energy\",\"syncopation\",\"swing\",\"variation\""
                        + "]"
                        + "}"
                        + "}");
    }

    public static final class FakeEnvironment {
    }

    public static final class FakeTensor {
        final float[] values;
        final long[] shape;

        FakeTensor(FloatBuffer source, long[] shape) {
            final FloatBuffer copy = source.duplicate();
            values = new float[copy.remaining()];
            copy.get(values);
            this.shape = shape.clone();
        }
    }

    public static final class FakeTensorFactory {
        public static FakeTensor createTensor(
                FakeEnvironment environment,
                FloatBuffer buffer,
                long[] shape) {
            return new FakeTensor(buffer, shape);
        }
    }

    public static final class FakeRemiSession {
        private final Map<String, Object> inputInfo = new LinkedHashMap<>();
        private final Map<String, Object> outputInfo = new LinkedHashMap<>();

        FakeRemiSession(int vocabularySize) {
            inputInfo.put("input_ids",
                    new FakeNodeInfo("tensor(int64)", new long[] {1L, -1L}));
            outputInfo.put("logits",
                    new FakeNodeInfo("tensor(float)", new long[] {1L, vocabularySize}));
        }

        public Map<String, Object> getInputInfo() {
            return inputInfo;
        }

        public Map<String, Object> getOutputInfo() {
            return outputInfo;
        }
    }

    public static final class FakeSession {
        private final Map<String, Object> inputInfo =
                new LinkedHashMap<>();
        private final Map<String, Object> outputInfo =
                new LinkedHashMap<>();

        FakeSession(
                boolean includeAllInputs,
                boolean mismatchPerformanceControls) {
            inputInfo.put(
                    "input_ids",
                    new FakeNodeInfo(
                            "tensor(int64)",
                            new long[] {1L, -1L}));

            if (includeAllInputs) {
                inputInfo.put(
                        "style_id",
                        new FakeNodeInfo("tensor(int64)", new long[] {1L}));
                inputInfo.put(
                        "substyle_id",
                        new FakeNodeInfo("tensor(int64)", new long[] {1L}));
                inputInfo.put(
                        "mood_id",
                        new FakeNodeInfo("tensor(int64)", new long[] {1L}));
                inputInfo.put(
                        "rhythm_id",
                        new FakeNodeInfo("tensor(int64)", new long[] {1L}));
                inputInfo.put(
                        "role_id",
                        new FakeNodeInfo("tensor(int64)", new long[] {1L}));
                inputInfo.put(
                        "performance_controls",
                        new FakeNodeInfo(
                                mismatchPerformanceControls
                                        ? "tensor(int64)"
                                        : "tensor(float)",
                                mismatchPerformanceControls
                                        ? new long[] {1L, 5L}
                                        : new long[] {1L, 5L}));
            }

            outputInfo.put(
                    "logits",
                    new FakeNodeInfo(
                            "tensor(float)",
                            new long[] {1L, 1L, 512L}));
        }

        public Map<String, Object> getInputInfo() {
            return inputInfo;
        }

        public Map<String, Object> getOutputInfo() {
            return outputInfo;
        }
    }

    public static final class FakeNodeInfo {
        private final FakeValueInfo info;

        FakeNodeInfo(String type, long[] shape) {
            info = new FakeValueInfo(type, shape);
        }

        public FakeValueInfo getInfo() {
            return info;
        }
    }

    public static final class FakeValueInfo {
        private final String type;
        private final long[] shape;

        FakeValueInfo(String type, long[] shape) {
            this.type = type;
            this.shape = shape;
        }

        public String getType() {
            return type;
        }

        public long[] getShape() {
            return shape.clone();
        }
    }


    @Test
    public void remiBpeRejectsTheLegacy512Vocabulary() throws Exception {
        final JSONObject manifest = new JSONObject();
        manifest.put("manifest_schema_version", 1);
        manifest.put("model_format", "onnx");
        manifest.put("vocabulary_id", "mozart-midi-events-v1");
        manifest.put("vocabulary_size", 512);
        manifest.put("context_length_tokens", 16);
        manifest.put("max_generated_tokens", 8);
        try {
            validateRemiManifestForTest(manifest);
            fail("expected external vocabulary rejection");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("vocabulary or length"));
        }
    }

    @Test
    public void remiBpeRejectsMozartTokenModeEvenWithMatchingExternalSize() throws Exception {
        final JSONObject manifest = new JSONObject();
        manifest.put("manifest_schema_version", 1);
        manifest.put("model_format", "onnx");
        manifest.put("vocabulary_id", "miditok-remi-bpe-v1");
        manifest.put("vocabulary_size", 23);
        manifest.put("context_length_tokens", 16);
        manifest.put("max_generated_tokens", 8);
        final JSONObject runtime = new JSONObject();
        runtime.put("backend", "onnxruntime");
        runtime.put("token_mode", "mozart_ids");
        runtime.put("external_vocabulary_size", 23);
        runtime.put("input_dtype", "int64");
        manifest.put("runtime", runtime);
        try {
            validateRemiManifestForTest(manifest);
            fail("expected REMI token-mode rejection");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("REMI/BPE ONNX token ABI"));
        }
    }

    @Test
    public void remiBpeArgmaxKeepsEosAvailableAndMasksOnlySpecialTokens() throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "argmaxRemiBpeToken", double[].class, int.class, int.class, int.class);
        method.setAccessible(true);
        // PAD, BOS and MASK outscore EOS, but EOS must remain a valid next token.
        final int next = (Integer) method.invoke(null,
                new double[] {100.0, 90.0, 80.0, 95.0, 1.0},
                0, 1, 3);
        assertEquals(2, next);
    }

    @Test
    public void remiBpeRejectsRuntimeGenerationLimitsThatDisagreeWithRootManifest()
            throws Exception {
        final JSONObject manifest = new JSONObject();
        manifest.put("manifest_schema_version", 1);
        manifest.put("model_format", "onnx");
        manifest.put("vocabulary_id", "miditok-remi-bpe-v1");
        manifest.put("vocabulary_size", 23);
        manifest.put("context_length_tokens", 16);
        manifest.put("max_generated_tokens", 8);

        final JSONObject runtime = new JSONObject();
        runtime.put("backend", "onnxruntime");
        runtime.put("token_mode", "remi_bpe");
        runtime.put("external_vocabulary_size", 23);
        runtime.put("input_dtype", "int64");
        runtime.put("context_length_tokens", 32);
        runtime.put("max_generated_tokens", 8);
        manifest.put("runtime", runtime);

        try {
            validateRemiManifestForTest(manifest);
            fail("expected runtime/root context mismatch rejection");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("runtime limits"));
        }
    }

    @Test
    public void remiBpeManifestAcceptsRealExternalTwentyThousandTokenAbi() throws Exception {
        final File directory = Files.createTempDirectory("mozart-remi-bpe-manifest-ok").toFile();
        directory.deleteOnExit();
        final File artifact = writeTempFile(directory, "model.onnx", "synthetic onnx bytes");
        final File tokenizer = writeTempFile(directory, "tokenizer.json", "synthetic learned bpe tokenizer bytes");
        final File manifestFile = new File(directory, "model.manifest.json");
        final JSONObject manifest = validRemiBpeManifest(artifact, tokenizer, 20000);

        validateRemiBpeManifestWithFiles(manifest, artifact, manifestFile, tokenizer);
    }

    @Test
    public void remiBpeManifestRejectsTokenizerHashMismatchBeforeSessionCreation() throws Exception {
        final File directory = Files.createTempDirectory("mozart-remi-bpe-manifest-hash").toFile();
        directory.deleteOnExit();
        final File artifact = writeTempFile(directory, "model.onnx", "synthetic onnx bytes");
        final File tokenizer = writeTempFile(directory, "tokenizer.json", "synthetic learned bpe tokenizer bytes");
        final JSONObject manifest = validRemiBpeManifest(artifact, tokenizer, 20000);
        manifest.getJSONObject("runtime").put("tokenizer_sha256", "0000000000000000000000000000000000000000000000000000000000000000");

        try {
            validateRemiBpeManifestWithFiles(manifest, artifact,
                    new File(directory, "model.manifest.json"), tokenizer);
            fail("expected tokenizer hash mismatch");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("tokenizer SHA-256"));
        }
    }

    @Test
    public void remiBpeManifestRejectsLegacySizedLogitsForExternalVocabulary() throws Exception {
        final File directory = Files.createTempDirectory("mozart-remi-bpe-manifest-shape").toFile();
        directory.deleteOnExit();
        final File artifact = writeTempFile(directory, "model.onnx", "synthetic onnx bytes");
        final File tokenizer = writeTempFile(directory, "tokenizer.json", "synthetic learned bpe tokenizer bytes");
        final JSONObject manifest = validRemiBpeManifest(artifact, tokenizer, 20000);
        manifest.getJSONArray("outputs").getJSONObject(0)
                .put("shape", new JSONArray(new int[] {1, 512}));

        try {
            validateRemiBpeManifestWithFiles(manifest, artifact,
                    new File(directory, "model.manifest.json"), tokenizer);
            fail("expected logits vocabulary shape mismatch");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("logits manifest"));
        }
    }

    private static File writeTempFile(File directory, String name, String content) throws Exception {
        final File file = new File(directory, name);
        Files.write(file.toPath(), content.getBytes(StandardCharsets.UTF_8));
        file.deleteOnExit();
        return file;
    }

    private static JSONObject validRemiBpeManifest(
            File artifact, File tokenizer, int vocabSize) throws Exception {
        final JSONObject root = new JSONObject();
        root.put("manifest_schema_version", 1);
        root.put("manifest_status", "frozen");
        root.put("model_id", "real-remi-bpe-contract-fixture");
        root.put("model_format", "onnx");
        root.put("model_file", artifact.getName());
        root.put("model_sha256", sha256ForTest(artifact));
        root.put("vocabulary_id", "miditok-remi-bpe-v1");
        root.put("vocabulary_size", vocabSize);
        root.put("context_length_tokens", 2048);
        root.put("max_generated_tokens", 400);

        final JSONArray inputs = new JSONArray();
        final JSONObject input = new JSONObject();
        input.put("name", "input_ids");
        input.put("dtype", "int64");
        input.put("shape", new JSONArray(new int[] {1, -1}));
        inputs.put(input);
        root.put("inputs", inputs);

        final JSONArray outputs = new JSONArray();
        final JSONObject output = new JSONObject();
        output.put("name", "logits");
        output.put("dtype", "float32");
        output.put("shape", new JSONArray(new int[] {1, vocabSize}));
        outputs.put(output);
        root.put("outputs", outputs);

        final JSONObject runtime = new JSONObject();
        runtime.put("backend", "onnxruntime");
        runtime.put("token_mode", "remi_bpe");
        runtime.put("external_vocabulary_size", vocabSize);
        runtime.put("input_dtype", "int64");
        runtime.put("input_name", "input_ids");
        runtime.put("output_name", "logits");
        runtime.put("context_length_tokens", 2048);
        runtime.put("max_generated_tokens", 400);
        runtime.put("pad_token_id", 0);
        runtime.put("bos_token_id", 1);
        runtime.put("eos_token_id", 2);
        runtime.put("tokenizer_file", tokenizer.getName());
        runtime.put("tokenizer_sha256", sha256ForTest(tokenizer));
        root.put("runtime", runtime);
        return root;
    }

    private static String sha256ForTest(File file) throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod("sha256", File.class);
        method.setAccessible(true);
        return (String) method.invoke(null, file);
    }

    private static void validateRemiBpeManifestWithFiles(
            JSONObject root, File artifact, File manifest, File tokenizer) throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateRemiBpeManifest", JSONObject.class, File.class, File.class, File.class);
        method.setAccessible(true);
        try {
            method.invoke(null, root, artifact, manifest, tokenizer);
        } catch (InvocationTargetException wrapped) {
            final Throwable cause = wrapped.getCause();
            if (cause instanceof IllegalArgumentException) {
                throw (IllegalArgumentException) cause;
            }
            if (cause instanceof Exception) throw (Exception) cause;
            throw wrapped;
        }
    }

    @Test
    public void remiBpeSessionAbiAcceptsTwentyThousandLogits() throws Exception {
        final File directory = Files.createTempDirectory("mozart-remi-bpe-session-ok").toFile();
        directory.deleteOnExit();
        final File artifact = writeTempFile(directory, "model.onnx", "synthetic onnx bytes");
        final File tokenizer = writeTempFile(directory, "tokenizer.json", "synthetic learned bpe tokenizer bytes");
        final JSONObject manifest = validRemiBpeManifest(artifact, tokenizer, 20000);
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateRemiBpeSessionAbi", Object.class, JSONObject.class, int.class);
        method.setAccessible(true);

        method.invoke(null, new FakeRemiSession(20000), manifest, 20000);
    }

    @Test
    public void remiBpeSessionAbiRejectsLegacy512LogitsForTwentyThousandTokenizer() throws Exception {
        final File directory = Files.createTempDirectory("mozart-remi-bpe-session-mismatch").toFile();
        directory.deleteOnExit();
        final File artifact = writeTempFile(directory, "model.onnx", "synthetic onnx bytes");
        final File tokenizer = writeTempFile(directory, "tokenizer.json", "synthetic learned bpe tokenizer bytes");
        final JSONObject manifest = validRemiBpeManifest(artifact, tokenizer, 20000);
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateRemiBpeSessionAbi", Object.class, JSONObject.class, int.class);
        method.setAccessible(true);

        try {
            method.invoke(null, new FakeRemiSession(512), manifest, 20000);
            fail("expected ONNX session logits shape mismatch");
        } catch (InvocationTargetException expected) {
            assertTrue(expected.getCause() instanceof IllegalArgumentException);
            assertTrue(expected.getCause().getMessage().contains("shape"));
        }
    }

    private static void validateRemiManifestForTest(JSONObject root) throws Exception {
        final Method method = OnnxInferenceBridge.class.getDeclaredMethod(
                "validateRemiBpeManifest", JSONObject.class,
                java.io.File.class, java.io.File.class, java.io.File.class);
        method.setAccessible(true);
        try {
            method.invoke(null, root, new java.io.File("missing.onnx"),
                    new java.io.File("missing-manifest.json"),
                    new java.io.File("missing-tokenizer.json"));
        } catch (InvocationTargetException wrapped) {
            final Throwable cause = wrapped.getCause();
            if (cause instanceof IllegalArgumentException) {
                throw (IllegalArgumentException) cause;
            }
            if (cause instanceof Exception) throw (Exception) cause;
            throw wrapped;
        }
    }

}
