package com.miguelduval.mozart;

import android.content.Context;
import android.graphics.Color;

/**
 * Единый источник визуальных токенов MPC One стиля.
 * Все цветовые токены должны определяться здесь, локальные палитры не вводятся.
 */
public final class MpcStyle {

    // Фоновые цвета
    public static final int PANEL_1 = Color.parseColor("#1A1A1A");
    public static final int PANEL_2 = Color.parseColor("#2A2A2A");
    public static final int PANEL_3 = Color.parseColor("#333333");

    // Акцентные цвета
    public static final int ACCENT_PRIMARY = Color.parseColor("#00FF88");
    public static final int ACCENT_SECONDARY = Color.parseColor("#0088FF");
    public static final int ACCENT_WARNING = Color.parseColor("#FFB800");

    // Текстовые цвета
    public static final int TEXT_PRIMARY = Color.parseColor("#FFFFFF");
    public static final int TEXT_SECONDARY = Color.parseColor("#B0B0B0");
    public static final int TEXT_DISABLED = Color.parseColor("#555555");

    // Режимы Touch Strip
    public static final int TOUCH_STRIP_MODE_LEVEL = 0;
    public static final int TOUCH_STRIP_MODE_PAN = 1;
    public static final int TOUCH_STRIP_MODE_TUNE = 2;
    public static final int TOUCH_STRIP_MODE_SAMPLE_START = 3;
    public static final int TOUCH_STRIP_MODE_SAMPLE_END = 4;

    private MpcStyle() {
    }
}
