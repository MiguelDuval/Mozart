package com.miguelduval.mozart;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.FloatBuffer;
import java.util.LinkedHashMap;
import java.util.Map;

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
                new String[] {
                        "style_id",
                        "substyle_id",
                        "mood_id",
                        "rhythm_id",
                        "role_id",
                        "performance_controls"
                });
        runtime.put(
                "performance_control_names",
                new String[] {
                        "density",
                        "energy",
                        "syncopation",
                        "swing",
                        "variation"
                });

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
                        + "\"input_dtype\":\"int64\""
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

}
