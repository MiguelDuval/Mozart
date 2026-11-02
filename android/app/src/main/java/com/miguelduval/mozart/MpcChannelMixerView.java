package com.miguelduval.mozart;

import android.content.Context;
import android.util.AttributeSet;
import android.widget.LinearLayout;

/**
 * Представление микшера каналов MPC One.
 * Управляет уровнем (level) и панорамированием (pan) для каждого трека.
 */
public class MpcChannelMixerView extends LinearLayout {

    /**
     * Фокус управления микшера каналов — соответствует фокусу Data Dial.
     */
    public enum ControlFocus {
        NONE,
        LEVEL,
        PAN,
        TUNE,
        SAMPLE_START,
        SAMPLE_END
    }

    private ControlFocus controlFocus = ControlFocus.NONE;

    public MpcChannelMixerView(Context context) {
        super(context);
    }

    public MpcChannelMixerView(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    public MpcChannelMixerView(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
    }

    public ControlFocus getControlFocus() {
        return controlFocus;
    }

    /**
     * Устанавливает фокус управления. Выполняет явное отображение
     * MpcUiState.DataDialFocus на MpcChannelMixerView.ControlFocus.
     */
    public void setControlFocus(ControlFocus focus) {
        this.controlFocus = focus;
    }

    /**
     * Преобразует DataDialFocus в ControlFocus.
     * CHANNEL_MIXER_LEVEL -> LEVEL, CHANNEL_MIXER_PAN -> PAN.
     */
    public static ControlFocus fromDataDialFocus(MpcUiState.DataDialFocus focus) {
        switch (focus) {
            case LEVEL:
                return ControlFocus.LEVEL;
            case PAN:
                return ControlFocus.PAN;
            case TUNE:
                return ControlFocus.TUNE;
            case SAMPLE_START:
                return ControlFocus.SAMPLE_START;
            case SAMPLE_END:
                return ControlFocus.SAMPLE_END;
            case NONE:
            default:
                return ControlFocus.NONE;
        }
    }

    /**
     * Преобразует ControlFocus обратно в DataDialFocus.
     */
    public static MpcUiState.DataDialFocus toDataDialFocus(ControlFocus focus) {
        switch (focus) {
            case LEVEL:
                return MpcUiState.DataDialFocus.LEVEL;
            case PAN:
                return MpcUiState.DataDialFocus.PAN;
            case TUNE:
                return MpcUiState.DataDialFocus.TUNE;
            case SAMPLE_START:
                return MpcUiState.DataDialFocus.SAMPLE_START;
            case SAMPLE_END:
                return MpcUiState.DataDialFocus.SAMPLE_END;
            case NONE:
            default:
                return MpcUiState.DataDialFocus.NONE;
        }
    }
}
