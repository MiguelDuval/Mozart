package com.miguelduval.mozart;

/**
 * Состояние пользовательского интерфейса MPC One.
 * Является единым источником фокуса Data Dial и других UI-параметров.
 */
public final class MpcUiState {

    /**
     * Фокус Data Dial — определяет, какой параметр сейчас управляется вращением Data Dial.
     */
    public enum DataDialFocus {
        NONE,
        LEVEL,
        PAN,
        TUNE,
        SAMPLE_START,
        SAMPLE_END,
        TEMPO,
        VOLUME
    }

    private DataDialFocus dataDialFocus = DataDialFocus.NONE;

    private MpcUiState() {
    }

    private static final MpcUiState INSTANCE = new MpcUiState();

    public static MpcUiState getInstance() {
        return INSTANCE;
    }

    public DataDialFocus getDataDialFocus() {
        return dataDialFocus;
    }

    public void setDataDialFocus(DataDialFocus focus) {
        this.dataDialFocus = focus;
    }
}
