package com.miguelduval.mozart;

/**
 * Вспомогательный класс для Touch Strip.
 * Содержит единственную реализацию touchStripModeLabel,
 * избегающую дублирования магических чисел.
 */
public final class TouchStripHelper {

    private TouchStripHelper() {
    }

    /**
     * Возвращает читаемую метку режима Touch Strip.
     * Использует именованные константы MpcStyle.TOUCH_STRIP_MODE_*.
     */
    public static String touchStripModeLabel(int mode) {
        switch (mode) {
            case MpcStyle.TOUCH_STRIP_MODE_LEVEL:
                return "Level";
            case MpcStyle.TOUCH_STRIP_MODE_PAN:
                return "Pan";
            case MpcStyle.TOUCH_STRIP_MODE_TUNE:
                return "Tune";
            case MpcStyle.TOUCH_STRIP_MODE_SAMPLE_START:
                return "Sample Start";
            case MpcStyle.TOUCH_STRIP_MODE_SAMPLE_END:
                return "Sample End";
            default:
                return "Unknown";
        }
    }
}
