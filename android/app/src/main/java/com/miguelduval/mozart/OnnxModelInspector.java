package com.miguelduval.mozart;

import java.io.File;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.util.Locale;
import java.util.Map;

public final class OnnxModelInspector {
    private OnnxModelInspector() {}

    public static String inspect(File modelFile) {
        if (modelFile == null || !modelFile.isFile()) {
            return "ONNX: model artifact not found.";
        }

        try {
            final Class<?> envClass =
                    Class.forName("ai.onnxruntime.OrtEnvironment");
            final Object environment =
                    envClass.getMethod("getEnvironment").invoke(null);

            final Method createSession =
                    envClass.getMethod("createSession", String.class);
            final Object session =
                    createSession.invoke(environment, modelFile.getAbsolutePath());

            try {
                final StringBuilder result = new StringBuilder();
                result.append("ONNX Runtime: ")
                        .append(getVersion(environment))
                        .append("\n");
                result.append("MODEL: ")
                        .append(modelFile.getName())
                        .append("\n\n");

                appendNodes(result, session, "INPUTS", "getInputInfo");
                appendNodes(result, session, "OUTPUTS", "getOutputInfo");
                return result.toString();
            } finally {
                closeQuietly(session);
            }
        } catch (ClassNotFoundException e) {
            return "ONNX Runtime unavailable in this build.\n"
                    + "Use the debug build with ONNX Runtime enabled.";
        } catch (Throwable e) {
            final String message =
                    e.getCause() != null
                            ? e.getCause().getMessage()
                            : e.getMessage();
            return "ONNX inspection failed: "
                    + (message == null ? e.getClass().getSimpleName() : message);
        }
    }

    private static String getVersion(Object environment) {
        try {
            return String.valueOf(
                    environment.getClass().getMethod("getVersion").invoke(environment));
        } catch (Throwable ignored) {
            return "unknown";
        }
    }

    @SuppressWarnings("unchecked")
    private static void appendNodes(
            StringBuilder result,
            Object session,
            String title,
            String methodName) throws Exception {
        result.append(title).append(":\n");

        final Map<String, ?> nodes =
                (Map<String, ?>) session.getClass()
                        .getMethod(methodName)
                        .invoke(session);

        if (nodes.isEmpty()) {
            result.append("  none\n\n");
            return;
        }

        for (Map.Entry<String, ?> entry : nodes.entrySet()) {
            final Object nodeInfo = entry.getValue();
            final Object valueInfo =
                    nodeInfo.getClass().getMethod("getInfo").invoke(nodeInfo);

            result.append("  ")
                    .append(entry.getKey())
                    .append(" type=")
                    .append(invokeType(valueInfo))
                    .append(" shape=")
                    .append(invokeShape(valueInfo))
                    .append("\n");
        }

        result.append("\n");
    }

    private static String invokeType(Object valueInfo) {
        try {
            return String.valueOf(
                    valueInfo.getClass().getMethod("getType").invoke(valueInfo))
                    .toLowerCase(Locale.ROOT);
        } catch (Throwable ignored) {
            return "unknown";
        }
    }

    private static String invokeShape(Object valueInfo) {
        try {
            final Object shape =
                    valueInfo.getClass().getMethod("getShape").invoke(valueInfo);
            if (shape == null || !shape.getClass().isArray()) {
                return "unknown";
            }

            final int length = Array.getLength(shape);
            final StringBuilder result = new StringBuilder("[");
            for (int i = 0; i < length; ++i) {
                if (i > 0) {
                    result.append(", ");
                }
                result.append(Array.getLong(shape, i));
            }
            return result.append("]").toString();
        } catch (Throwable ignored) {
            return "unknown";
        }
    }

    private static void closeQuietly(Object value) {
        if (!(value instanceof AutoCloseable)) {
            return;
        }

        try {
            ((AutoCloseable) value).close();
        } catch (Exception ignored) {
            // Best-effort cleanup for an inspector-only debug path.
        }
    }
}
