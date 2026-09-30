package com.miguelduval.mozart;

import android.app.Activity;
import android.Manifest;
import android.content.pm.PackageManager;
import android.content.pm.ApplicationInfo;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class MainActivity extends Activity {
    private static final String TAG = "MozartStartup";
    private static final String RUNTIME_SMOKE_EXTRA = "mozart.runtime_smoke";
    private static final long LINK_STATUS_POLL_MS = 500L;
    private static final long MIDI_INPUT_STATUS_POLL_MS = 500L;
    private static final int RECORD_AUDIO_REQUEST = 7001;
    private static final String[] KEY_LABELS = {
            "C", "C#", "D", "D#", "E", "F",
            "F#", "G", "G#", "A", "A#", "B"
    };
    private static final String[] SCALE_LABELS = {"MAJOR", "MINOR", "DORIAN"};
    static {
        Log.i(TAG, "STARTUP: loadLibrary begin");
        System.loadLibrary("mozart");
        Log.i(TAG, "STARTUP: loadLibrary complete");
    }

    private static native String nativeEngineInfo();
    private static native void nativeStartAccompaniment();
    private static native void nativeStopAccompaniment();
    private static native String nativeLinkSnapshot();
    private static native String nativeMidiInputSnapshot();
    private static native boolean nativeTestMidiNote();
    private static native void nativeSetAccompanimentRole(int role);
    private static native void nativeSetPerformanceScene(int sceneIndex);
    private static native void nativeRequestPatternMutation();
    private static native void nativeSetNoteRepeat(int rate);
    private static native void nativeSetMacro(int control, int value);
    private static native void nativeSetPatternDensity(int density);
    private static native void nativeSetPatternAccent(int accent);
    private static native void nativeSetPatternSwing(int swing);
    private static native void nativeSetManualKeyScale(
            int rootPitchClass,
            int scaleId);
    private static native void nativeSetKeyContextSource(int source);
    private static native void nativeResetAudioKeyContext();
    private static native String nativeKeyContextSnapshot();
    private static native boolean nativeRegisterExperimentalModel(
            String modelId,
            String displayName,
            String backendId,
            String artifactPath,
            String manifestPath);
    private static native boolean nativeSelectExperimentalModel(String modelId);
    private static native void nativeClearSelectedModel();
    private static native String nativeSelectedModelSnapshot();
    private static native boolean nativeQueueExperimentalGeneration();
    private static native String nativeExperimentalGenerationSnapshot();

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private TextView status;
    private TextView linkStatus;
    private TextView midiOutputStatus;
    private TextView midiInputStatus;
    private TextView keyContextStatus;
    private AndroidMidiTransport midiTransport;
    private AndroidMidiInput midiInput;
    private AndroidAudioKeyInput audioKeyInput;
    private Button midiInputButton;
    private Button keySourceButton;
    private ExperimentalModelLab experimentalModelLab;
    private String selectedExperimentalModelId = "";
    private List<AndroidMidiTransport.MidiEndpoint> midiInputCandidates = Collections.emptyList();
    private int midiInputSelection = -1;
    private boolean activityStarted = false;
    private int selectedRootPitchClass = 6;
    private int selectedScaleId = 1;
    private int selectedSceneIndex = 0;

    private final Runnable keyContextStatusPoll = new Runnable() {
        @Override
        public void run() {
            if (!activityStarted || keyContextStatus == null) {
                return;
            }
            keyContextStatus.setText(
                    "KEY CONTEXT: " + nativeKeyContextSnapshot());
            mainHandler.postDelayed(this, LINK_STATUS_POLL_MS);
        }
    };

    private final Runnable midiInputStatusPoll = new Runnable() {
        @Override
        public void run() {
            if (!activityStarted || midiInputStatus == null) {
                return;
            }
            midiInputStatus.setText("MIDI IN: " + nativeMidiInputSnapshot());
            mainHandler.postDelayed(this, MIDI_INPUT_STATUS_POLL_MS);
        }
    };

    private final Runnable generationPoll = new Runnable() {
        @Override
        public void run() {
            if (!activityStarted) {
                return;
            }
            final String snapshot = nativeExperimentalGenerationSnapshot();
            if (snapshot.startsWith("state=ready")) {
                appendStatus("AI TEST  " + snapshot);
                return;
            }
            if (snapshot.equals("state=queued")) {
                mainHandler.postDelayed(this, 250L);
            }
        }
    };

    private final Runnable linkStatusPoll = new Runnable() {
        @Override
        public void run() {
            if (!activityStarted || linkStatus == null) {
                return;
            }

            updateLinkStatus();
            mainHandler.postDelayed(this, LINK_STATUS_POLL_MS);
        }
    };

    private final AndroidMidiTransport.Listener midiListener =
            new AndroidMidiTransport.Listener() {
                @Override
                public void onMidiInventoryChanged(
                        List<AndroidMidiTransport.MidiEndpoint> endpoints,
                        AndroidMidiTransport.MidiEndpoint selectedOutput,
                        String connectionStatus) {
                    updateMidiStatus(
                            endpoints,
                            selectedOutput,
                            connectionStatus);
                }
            };

    @Override
    protected void onCreate(Bundle state) {
        Log.i(TAG, "STARTUP: onCreate begin");
        super.onCreate(state);

        final int bg = Color.rgb(11, 14, 19);
        final int panel = Color.rgb(20, 25, 32);
        final int panelAlt = Color.rgb(24, 30, 38);
        final int textPrimary = Color.rgb(239, 244, 248);
        final int textSecondary = Color.rgb(159, 173, 185);
        final int accent = Color.rgb(53, 214, 181);
        final int accentDark = Color.rgb(23, 92, 82);
        final int warning = Color.rgb(244, 181, 74);
        final int stopColor = Color.rgb(224, 92, 99);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg);
        root.setPadding(dp(10), dp(8), dp(10), dp(6));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);
        titleBlock.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = label("MOZART", 20.0f, textPrimary);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        TextView subtitle = label("LIVE ACCOMPANIST  •  LINK  •  MIDI", 10.0f, textSecondary);

        titleBlock.addView(title);
        titleBlock.addView(subtitle);

        header.addView(titleBlock, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        LinearLayout liveStatus = new LinearLayout(this);
        liveStatus.setOrientation(LinearLayout.VERTICAL);
        liveStatus.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);

        linkStatus = label("LINK  •  " + nativeLinkSnapshot(), 11.0f, accent);
        linkStatus.setGravity(Gravity.END);
        keyContextStatus = label("KEY  •  " + nativeKeyContextSnapshot(), 10.0f, textSecondary);
        keyContextStatus.setGravity(Gravity.END);

        liveStatus.addView(linkStatus);
        liveStatus.addView(keyContextStatus);
        header.addView(liveStatus);

        root.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));

        status = label("", 10.0f, textSecondary);
        status.setGravity(Gravity.CENTER_VERTICAL);
        status.setMaxLines(2);
        status.setEllipsize(android.text.TextUtils.TruncateAt.END);
        status.setPadding(dp(8), 0, dp(8), 0);
        status.setBackground(roundRect(panelAlt, dp(8), Color.TRANSPARENT, 0));
        Log.i(TAG, "STARTUP: nativeEngineInfo begin");
        final String engineInfo = nativeEngineInfo();
        Log.i(TAG, "STARTUP: nativeEngineInfo complete");
        status.setText("READY  •  " + engineInfo);

        root.addView(status, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(34)));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(true);
        scroll.setClipToPadding(false);

        LinearLayout columns = new LinearLayout(this);
        columns.setOrientation(LinearLayout.HORIZONTAL);
        columns.setPadding(0, dp(6), 0, dp(10));

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setPadding(0, 0, dp(4), 0);

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(dp(4), 0, 0, 0);

        columns.addView(left, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));
        columns.addView(right, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));
        scroll.addView(columns);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f));

        // ---- LEFT: musical context + transport ----
        LinearLayout contextCard = section("MUSICAL CONTEXT", panel, textSecondary);
        LinearLayout keyScaleRow = row();
        Button key = controlButton("KEY  F#", false, textPrimary, panelAlt);
        Button scale = controlButton("SCALE  MINOR", false, textPrimary, panelAlt);

        key.setOnClickListener(view -> {
            if (audioKeyInput != null && audioKeyInput.isRunning()) {
                audioKeyInput.stop();
            }
            nativeResetAudioKeyContext();
            nativeSetKeyContextSource(0);
            keySourceButton.setText("KEY SOURCE  MANUAL");
            selectedRootPitchClass = (selectedRootPitchClass + 1) % 12;
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            key.setText("KEY  " + KEY_LABELS[selectedRootPitchClass]);
            appendStatus("KEY  " + KEY_LABELS[selectedRootPitchClass]
                    + " • next bar");
        });

        scale.setOnClickListener(view -> {
            if (audioKeyInput != null && audioKeyInput.isRunning()) {
                audioKeyInput.stop();
            }
            nativeResetAudioKeyContext();
            nativeSetKeyContextSource(0);
            keySourceButton.setText("KEY SOURCE  MANUAL");
            selectedScaleId = (selectedScaleId + 1) % 3;
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            scale.setText("SCALE  " + SCALE_LABELS[selectedScaleId]);
            appendStatus("SCALE  " + SCALE_LABELS[selectedScaleId]
                    + " • next bar");
        });

        addEqual(keyScaleRow, key, scale);
        contextCard.addView(keyScaleRow);

        keySourceButton = controlButton("KEY SOURCE  MANUAL", false, textPrimary, panelAlt);
        keySourceButton.setOnClickListener(view -> {
            if (audioKeyInput == null) {
                return;
            }

            if (audioKeyInput.isRunning()) {
                audioKeyInput.stop();
                nativeResetAudioKeyContext();
                nativeSetKeyContextSource(0);
                keySourceButton.setText("KEY SOURCE  MANUAL");
                appendStatus("AUDIO KEY  OFF");
                return;
            }

            if (android.os.Build.VERSION.SDK_INT >= 23 &&
                    checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                            != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                        new String[]{Manifest.permission.RECORD_AUDIO},
                        RECORD_AUDIO_REQUEST);
                appendStatus("MIC PERMISSION  REQUIRED");
                return;
            }

            if (audioKeyInput.start()) {
                nativeResetAudioKeyContext();
                nativeSetKeyContextSource(1);
                keySourceButton.setText("KEY SOURCE  AUDIO");
                appendStatus("AUDIO KEY  ON • waiting for stable result");
            } else {
                appendStatus("AUDIO KEY  could not start");
            }
        });
        contextCard.addView(keySourceButton);

        left.addView(contextCard, sectionParams());

        LinearLayout transportCard = section("LINK & TRANSPORT", panel, textSecondary);
        transportCard.addView(label("LINK", 9.0f, textSecondary));
        Button start = controlButton("START LINK", true, textPrimary, accentDark);
        start.setOnClickListener(view -> {
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            nativeStartAccompaniment();
            appendStatus("ACCOMPANIMENT  STARTED");
            updateLinkStatus();
        });

        Button stop = controlButton("STOP", true, textPrimary, stopColor);
        stop.setOnClickListener(view -> {
            nativeStopAccompaniment();
            appendStatus("ACCOMPANIMENT  STOPPED");
            updateLinkStatus();
        });

        LinearLayout transportButtons = row();
        addEqual(transportButtons, start, stop);
        transportCard.addView(transportButtons);

        midiOutputStatus = label("MIDI OUT  •  discovering...", 10.0f, textSecondary);
        midiOutputStatus.setGravity(Gravity.CENTER_VERTICAL);
        midiOutputStatus.setMaxLines(2);
        midiOutputStatus.setEllipsize(android.text.TextUtils.TruncateAt.END);
        transportCard.addView(midiOutputStatus, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(32)));

        Button testMidi = controlButton("TEST MIDI OUT", true, textPrimary, warning);
        testMidi.setOnClickListener(view -> {
            final boolean queued = nativeTestMidiNote();
            appendStatus(queued
                    ? "TEST MIDI  C2 QUEUED"
                    : "TEST MIDI  FAILED • check MIDI OUT");
        });
        transportCard.addView(testMidi);

        left.addView(transportCard, sectionParams());

        LinearLayout midiInCard = section("MIDI INPUT", panel, textSecondary);
        midiInputButton = controlButton("MIDI IN  OFF", false, textPrimary, panelAlt);
        midiInputButton.setOnClickListener(view -> cycleMidiInputSource());
        midiInCard.addView(midiInputButton);

        midiInputStatus = label("MIDI IN  •  pending=0 received=0 dropped=0", 10.0f, textSecondary);
        midiInputStatus.setMaxLines(2);
        midiInputStatus.setEllipsize(android.text.TextUtils.TruncateAt.END);
        midiInCard.addView(midiInputStatus, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(32)));
        left.addView(midiInCard, sectionParams());

        // ---- RIGHT: performance controls ----
        LinearLayout roleCard = section("ACCOMPANIMENT", panel, textSecondary);
        LinearLayout roleRow = row();
        Button bass = controlButton("BASS", false, textPrimary, panelAlt);
        Button arpeggio = controlButton("ARPEGGIO", false, textPrimary, panelAlt);
        Button drums = controlButton("DRUMS", false, textPrimary, panelAlt);

        bass.setOnClickListener(view -> {
            nativeSetAccompanimentRole(0);
            appendStatus("ROLE  BASS • next bar");
        });
        arpeggio.setOnClickListener(view -> {
            nativeSetAccompanimentRole(1);
            appendStatus("ROLE  ARPEGGIO • next bar");
        });
        drums.setOnClickListener(view -> {
            nativeSetAccompanimentRole(2);
            appendStatus("ROLE  DRUMS • next bar");
        });

        addEqual(roleRow, bass, arpeggio, drums);
        roleCard.addView(roleRow);

        Button scene = controlButton("SCENE  1", false, textPrimary, panelAlt);
        scene.setOnClickListener(view -> {
            selectedSceneIndex = (selectedSceneIndex + 1) % 4;
            nativeSetPerformanceScene(selectedSceneIndex);
            scene.setText("SCENE  " + (selectedSceneIndex + 1));
            appendStatus("SCENE  " + (selectedSceneIndex + 1) + " • next bar");
        });
        roleCard.addView(scene);

        Button mutate = controlButton("MUTATE", true, textPrimary, accentDark);
        mutate.setOnClickListener(view -> {
            nativeRequestPatternMutation();
            appendStatus("MUTATION  REQUESTED • next bar");
        });
        roleCard.addView(mutate);

        LinearLayout rhythmRow = row();
        Button density = controlButton("DENSITY  FULL", false, textPrimary, panelAlt);
        final int[] densityIndex = {2};
        density.setOnClickListener(view -> {
            densityIndex[0] = (densityIndex[0] + 1) % 3;
            final int selectedDensity = densityIndex[0];
            nativeSetPatternDensity(selectedDensity);
            final String[] labels = {"DENSITY  SPARSE", "DENSITY  NORMAL", "DENSITY  FULL"};
            density.setText(labels[selectedDensity]);
            appendStatus(labels[selectedDensity] + " • next bar");
        });

        Button accentButton = controlButton("ACCENT  OFF", false, textPrimary, panelAlt);
        final int[] accentIndex = {0};
        accentButton.setOnClickListener(view -> {
            accentIndex[0] = (accentIndex[0] + 1) % 3;
            final int selectedAccent = accentIndex[0];
            nativeSetPatternAccent(selectedAccent);
            final String[] labels = {"ACCENT  OFF", "ACCENT  MILD", "ACCENT  STRONG"};
            accentButton.setText(labels[selectedAccent]);
            appendStatus(labels[selectedAccent] + " • next bar");
        });

        Button swing = controlButton("SWING  OFF", false, textPrimary, panelAlt);
        final int[] swingIndex = {0};
        swing.setOnClickListener(view -> {
            swingIndex[0] = (swingIndex[0] + 1) % 3;
            final int selectedSwing = swingIndex[0];
            nativeSetPatternSwing(selectedSwing);
            final String[] labels = {"SWING  OFF", "SWING  LIGHT", "SWING  FULL"};
            swing.setText(labels[selectedSwing]);
            appendStatus(labels[selectedSwing] + " • next bar");
        });

        addEqual(rhythmRow, density, accentButton, swing);
        roleCard.addView(rhythmRow);
        right.addView(roleCard, sectionParams());

        LinearLayout macroCard = section("MACROS & REPEAT", panel, textSecondary);
        LinearLayout macroRow = row();

        Button noteRepeat = controlButton("REPEAT  OFF", false, textPrimary, panelAlt);
        final int[] noteRepeatRate = {1};
        noteRepeat.setOnClickListener(view -> {
            noteRepeatRate[0]++;
            if (noteRepeatRate[0] > 4) {
                noteRepeatRate[0] = 1;
            }
            nativeSetNoteRepeat(noteRepeatRate[0]);
            final String[] labels = {
                    "REPEAT  OFF",
                    "REPEAT  2X",
                    "REPEAT  3X",
                    "REPEAT  4X"
            };
            noteRepeat.setText(labels[noteRepeatRate[0] - 1]);
            appendStatus(labels[noteRepeatRate[0] - 1] + " • next bar");
        });

        Button energy = controlButton("ENERGY  LOW", false, textPrimary, panelAlt);
        final int[] energyIndex = {0};
        energy.setOnClickListener(view -> {
            energyIndex[0] = (energyIndex[0] + 1) % 3;
            final int value = energyIndex[0] == 0 ? 0 : (energyIndex[0] == 1 ? 64 : 127);
            nativeSetMacro(0, value);
            final String[] labels = {"ENERGY  LOW", "ENERGY  MID", "ENERGY  HIGH"};
            energy.setText(labels[energyIndex[0]]);
            appendStatus(labels[energyIndex[0]] + " • next bar");
        });

        Button motion = controlButton("MOTION  LOW", false, textPrimary, panelAlt);
        final int[] motionIndex = {0};
        motion.setOnClickListener(view -> {
            motionIndex[0] = (motionIndex[0] + 1) % 3;
            final int value = motionIndex[0] == 0 ? 0 : (motionIndex[0] == 1 ? 64 : 127);
            nativeSetMacro(1, value);
            final String[] labels = {"MOTION  LOW", "MOTION  MID", "MOTION  HIGH"};
            motion.setText(labels[motionIndex[0]]);
            appendStatus(labels[motionIndex[0]] + " • next bar");
        });

        addEqual(macroRow, noteRepeat, energy, motion);
        macroCard.addView(macroRow);
        right.addView(macroCard, sectionParams());

        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            LinearLayout labCard = section("EXPERIMENTAL / DEBUG", panel, textSecondary);
            Button experimentalModels = controlButton("EXPERIMENTAL MODELS", false, textPrimary, panelAlt);
            experimentalModels.setOnClickListener(view -> experimentalModelLab.show());
            labCard.addView(experimentalModels);

            Button clearModel = controlButton("CLEAR MODEL SELECTION", false, textSecondary, panelAlt);
            clearModel.setOnClickListener(view -> {
                nativeClearSelectedModel();
                selectedExperimentalModelId = "";
                appendStatus("EXPERIMENTAL MODEL  CLEARED");
            });
            labCard.addView(clearModel);

            Button aiTest = controlButton("RUN AI GENERATION TEST", true, textPrimary, panelAlt);
            aiTest.setOnClickListener(view -> {
                final boolean queued = nativeQueueExperimentalGeneration();
                if (queued) {
                    appendStatus("AI TEST  QUEUED • worker thread");
                    mainHandler.post(generationPoll);
                } else {
                    appendStatus(
                            "AI TEST  NOT QUEUED • select a ready experimental model");
                }
            });
            labCard.addView(aiTest);
            right.addView(labCard, sectionParams());
        }

        setContentView(root);
        Log.i(TAG, "STARTUP: setContentView complete");

        if (getIntent().getBooleanExtra(RUNTIME_SMOKE_EXTRA, false)) {
            startRuntimeSmoke();
        }

        midiTransport = new AndroidMidiTransport(this, midiListener);
        midiInput = new AndroidMidiInput(
                this,
                message -> appendStatus(message));
        audioKeyInput = new AndroidAudioKeyInput();
        experimentalModelLab = new ExperimentalModelLab(
                this,
                model -> {
                    nativeRegisterExperimentalModel(
                            model.modelId,
                            model.displayName,
                            model.backendId,
                            model.artifactPath,
                            model.manifestPath);
                    final boolean selected = nativeSelectExperimentalModel(model.modelId);
                    if (selected) {
                        selectedExperimentalModelId = model.modelId;
                        appendStatus("MODEL  " + model.modelId + " SELECTED");
                    } else {
                        appendStatus("MODEL  " + model.modelId + " NOT SELECTED");
                    }
                });
        Log.i(TAG, "STARTUP: AndroidMidiTransport constructed");
        Log.i(TAG, "STARTUP: AndroidMidiInput constructed");
        Log.i(TAG, "STARTUP: onCreate complete");
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView label(String text, float sizeSp, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }

    private LinearLayout section(String title, int backgroundColor, int secondaryColor) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(8), dp(10), dp(8));
        card.setBackground(roundRect(backgroundColor, dp(12), Color.rgb(49, 59, 70), dp(1)));

        TextView heading = label(title, 10.0f, secondaryColor);
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        card.addView(heading, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(18)));
        return card;
    }

    private LinearLayout.LayoutParams sectionParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, dp(6));
        return params;
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    private void addEqual(LinearLayout row, Button... buttons) {
        for (Button button : buttons) {
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    0, dp(38), 1.0f);
            params.setMargins(dp(2), dp(2), dp(2), dp(2));
            row.addView(button, params);
        }
    }

    private Button controlButton(
            String text,
            boolean emphasized,
            int textColor,
            int fillColor) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextColor(textColor);
        button.setTextSize(10.5f);
        button.setGravity(Gravity.CENTER);
        button.setAllCaps(false);
        button.setSingleLine(true);
        button.setEllipsize(android.text.TextUtils.TruncateAt.END);
        button.setTypeface(Typeface.DEFAULT, emphasized
                ? Typeface.BOLD
                : Typeface.NORMAL);
        button.setMinHeight(dp(38));
        button.setMinimumHeight(dp(38));
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(6), 0, dp(6), 0);
        button.setBackground(roundRect(fillColor, dp(9), Color.rgb(59, 70, 82), dp(1)));
        return button;
    }

    private GradientDrawable roundRect(
            int fillColor,
            int radius,
            int strokeColor,
            int strokeWidth) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(radius);
        if (strokeWidth > 0) {
            drawable.setStroke(strokeWidth, strokeColor);
        }
        return drawable;
    }

    private void appendStatus(String message) {
        if (status == null || message == null) {
            return;
        }

        String clean = message.trim();
        if (clean.isEmpty()) {
            return;
        }

        String current = status.getText() == null
                ? ""
                : status.getText().toString().trim();
        if (current.startsWith("READY") && current.contains("Engine")) {
            current = "";
        }

        String combined = current.isEmpty()
                ? clean
                : current + "\n" + clean;

        String[] lines = combined.split("\\n");
        int first = Math.max(0, lines.length - 2);
        StringBuilder visible = new StringBuilder();
        for (int i = first; i < lines.length; ++i) {
            if (visible.length() > 0) {
                visible.append("\n");
            }
            visible.append(lines[i]);
        }
        status.setText(visible.toString());
    }

    private void startRuntimeSmoke() {
        Log.i(TAG, "RUNTIME: Android smoke start begin");
        nativeSetManualKeyScale(6, 1);
        nativeStartAccompaniment();
        Log.i(TAG, "RUNTIME: Android smoke start complete");
        Log.i(TAG, "RUNTIME: Link snapshot initial " + nativeLinkSnapshot());

        mainHandler.postDelayed(
                () -> Log.i(
                        TAG,
                        "RUNTIME: Link snapshot tick " + nativeLinkSnapshot()),
                1000L);

        mainHandler.postDelayed(() -> {
            nativeStopAccompaniment();
            Log.i(TAG, "RUNTIME: Link snapshot stopped " + nativeLinkSnapshot());
            Log.i(TAG, "RUNTIME: Android smoke stop complete");
        }, 3000L);
    }

    @Override
    protected void onStart() {
        Log.i(TAG, "STARTUP: onStart begin");
        super.onStart();
        activityStarted = true;
        if (keySourceButton != null) {
            keySourceButton.setText(
                    audioKeyInput != null && audioKeyInput.isRunning()
                            ? "KEY SOURCE: AUDIO"
                            : "KEY SOURCE: MANUAL");
        }
        updateLinkStatus();
        midiInputStatus.setText("MIDI IN: " + nativeMidiInputSnapshot());
        mainHandler.removeCallbacks(linkStatusPoll);
        mainHandler.removeCallbacks(midiInputStatusPoll);
        mainHandler.removeCallbacks(keyContextStatusPoll);
        mainHandler.removeCallbacks(generationPoll);
        mainHandler.post(linkStatusPoll);
        mainHandler.post(keyContextStatusPoll);
        mainHandler.post(midiInputStatusPoll);
        if (midiTransport != null) {
            Log.i(TAG, "STARTUP: midiTransport.start posting");
            midiTransport.start();
        }
        Log.i(TAG, "STARTUP: onStart complete");
    }

    @Override
    protected void onStop() {
        activityStarted = false;
        mainHandler.removeCallbacks(linkStatusPoll);
        mainHandler.removeCallbacks(midiInputStatusPoll);
        mainHandler.removeCallbacks(keyContextStatusPoll);
        mainHandler.removeCallbacks(generationPoll);
        nativeStopAccompaniment();
        if (audioKeyInput != null) {
            audioKeyInput.stop();
        }
        nativeResetAudioKeyContext();
        nativeSetKeyContextSource(0);

        if (midiInput != null) {
            midiInput.close();
        }
        if (midiTransport != null) {
            midiTransport.stop();
        }
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        mainHandler.removeCallbacks(linkStatusPoll);
        mainHandler.removeCallbacks(midiInputStatusPoll);
        mainHandler.removeCallbacks(keyContextStatusPoll);
        mainHandler.removeCallbacks(generationPoll);
        if (audioKeyInput != null) {
            audioKeyInput.stop();
        }
        nativeResetAudioKeyContext();
        nativeSetKeyContextSource(0);
        if (midiInput != null) {
            midiInput.shutdown();
        }
        if (midiTransport != null) {
            midiTransport.shutdown();
        }
        super.onDestroy();
    }

    private void updateLinkStatus() {
        if (linkStatus != null) {
            linkStatus.setText("Link: " + nativeLinkSnapshot());
        }
    }

    private void updateMidiStatus(
            List<AndroidMidiTransport.MidiEndpoint> endpoints,
            AndroidMidiTransport.MidiEndpoint selectedOutput,
            String connectionStatus) {
        updateMidiInputCandidates(endpoints);

        if (midiOutputStatus != null) {
            final String output;
            if (selectedOutput == null) {
                output = "MIDI OUT  •  no MicroFreak selected";
            } else {
                output = "MIDI OUT  •  " + selectedOutput.displayName()
                        + (selectedOutput.isUsb() ? "  [USB]" : "  [NON-USB]");
            }
            midiOutputStatus.setText(output);
        }
        appendStatus("MIDI  " + connectionStatus
                + "  •  endpoints=" + endpoints.size());
    }

    private void updateMidiInputCandidates(
            List<AndroidMidiTransport.MidiEndpoint> endpoints) {
        final List<AndroidMidiTransport.MidiEndpoint> candidates =
                new ArrayList<>();
        for (AndroidMidiTransport.MidiEndpoint endpoint : endpoints) {
            if (endpoint.isDeviceOutput()) {
                candidates.add(endpoint);
            }
        }

        final AndroidMidiTransport.MidiEndpoint previousSelection =
                midiInputSelection >= 0 &&
                midiInputSelection < midiInputCandidates.size()
                        ? midiInputCandidates.get(midiInputSelection)
                        : null;

        midiInputCandidates = Collections.unmodifiableList(candidates);

        if (previousSelection != null) {
            int preservedIndex = -1;
            for (int i = 0; i < midiInputCandidates.size(); ++i) {
                if (sameEndpoint(previousSelection, midiInputCandidates.get(i))) {
                    preservedIndex = i;
                    break;
                }
            }
            midiInputSelection = preservedIndex;
        } else if (midiInputSelection >= midiInputCandidates.size()) {
            midiInputSelection = -1;
        }

        if (midiInputSelection < 0 && midiInput != null) {
            midiInput.close();
        }

        if (midiInputButton != null) {
            if (midiInputSelection < 0) {
                midiInputButton.setText("MIDI IN: OFF");
            } else {
                midiInputButton.setText(
                        "MIDI IN: " +
                                midiInputCandidates
                                        .get(midiInputSelection)
                                        .displayName());
            }
        }

        if (activityStarted &&
                midiInput != null &&
                midiInputSelection >= 0 &&
                midiInputSelection < midiInputCandidates.size()) {
            midiInput.open(midiInputCandidates.get(midiInputSelection));
        }
    }

    private static boolean sameEndpoint(
            AndroidMidiTransport.MidiEndpoint first,
            AndroidMidiTransport.MidiEndpoint second) {
        return first != null &&
                second != null &&
                first.deviceId == second.deviceId &&
                first.portNumber == second.portNumber;
    }

    private void cycleMidiInputSource() {
        if (midiInputCandidates.isEmpty()) {
            appendStatus("\n\nMIDI IN: no device OUTPUT ports discovered.");
            return;
        }

        midiInputSelection++;
        if (midiInputSelection >= midiInputCandidates.size()) {
            midiInputSelection = -1;
            midiInput.close();
            midiInputButton.setText("MIDI IN: OFF");
            appendStatus("\n\nMIDI IN disabled.");
            return;
        }

        final AndroidMidiTransport.MidiEndpoint endpoint =
                midiInputCandidates.get(midiInputSelection);
        midiInputButton.setText("MIDI IN: " + endpoint.displayName());
        midiInput.open(endpoint);
        appendStatus("\n\nMIDI IN source selected: " + endpoint.displayName());
    }
}
