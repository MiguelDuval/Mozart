package com.miguelduval.mozart;

import static org.junit.Assert.assertEquals;

import java.lang.reflect.Method;

import org.junit.Test;

public class OnnxInferenceBridgeTest {
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
