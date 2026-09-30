package com.miguelduval.mozart;

import static org.junit.Assert.assertEquals;

import java.lang.reflect.Method;

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
            assertEquals(
                    "ONNX logits vocabulary size must be 512",
                    expected.getCause().getMessage());
        }

        try {
            method.invoke(null, new Object[] {new double[513]});
            org.junit.Assert.fail("expected vocabulary mismatch");
        } catch (java.lang.reflect.InvocationTargetException expected) {
            assertEquals(
                    "ONNX logits vocabulary size must be 512",
                    expected.getCause().getMessage());
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
}
