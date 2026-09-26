package com.miguelduval.mozart;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.List;

public final class MainActivity extends Activity {
    private static final String TAG = "MozartStartup";
    private static final String RUNTIME_SMOKE_EXTRA = "mozart.runtime_smoke";
    private static final long LINK_STATUS_POLL_MS = 500L;
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
    private static native boolean nativeTestMidiNote();
    private static native void nativeSetAccompanimentRole(int role);
    private static native void nativeSetPatternDensity(int density);
    private static native void nativeSetPatternAccent(int accent);
    private static native void nativeSetPatternSwing(int swing);
    private static native void nativeSetManualKeyScale(
            int rootPitchClass,
            int scaleId);

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private TextView status;
    private TextView linkStatus;
    private AndroidMidiTransport midiTransport;
    private boolean activityStarted = false;
    private int selectedRootPitchClass = 6;
    private int selectedScaleId = 1;

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

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(48, 48, 48, 48);

        TextView title = new TextView(this);
        title.setText("MOZART");
        title.setTextSize(28.0f);
        title.setGravity(Gravity.CENTER);

        status = new TextView(this);
        Log.i(TAG, "STARTUP: nativeEngineInfo begin");
        final String engineInfo = nativeEngineInfo();
        Log.i(TAG, "STARTUP: nativeEngineInfo complete");
        status.setText("\n" + engineInfo
                + "\n\nMIDI discovery: waiting..."
                + "\nManual key: " + KEY_LABELS[selectedRootPitchClass]
                + " " + SCALE_LABELS[selectedScaleId]
                + "\nLink accompanist: stopped");
        status.setTextSize(16.0f);
        status.setGravity(Gravity.CENTER);

        linkStatus = new TextView(this);
        linkStatus.setText("Link: " + nativeLinkSnapshot());
        linkStatus.setTextSize(14.0f);
        linkStatus.setGravity(Gravity.CENTER);

        Button key = new Button(this);
        key.setText("KEY: F#");
        key.setOnClickListener(view -> {
            selectedRootPitchClass = (selectedRootPitchClass + 1) % 12;
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            key.setText("KEY: " + KEY_LABELS[selectedRootPitchClass]);
            status.append(
                    "\n\nKey: " + KEY_LABELS[selectedRootPitchClass]
                            + " selected; change takes effect at the next bar.");
        });

        Button scale = new Button(this);
        scale.setText("SCALE: MINOR");
        scale.setOnClickListener(view -> {
            selectedScaleId = (selectedScaleId + 1) % 3;
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            scale.setText("SCALE: " + SCALE_LABELS[selectedScaleId]);
            status.append(
                    "\n\nScale: " + SCALE_LABELS[selectedScaleId]
                            + " selected; change takes effect at the next bar.");
        });

        Button start = new Button(this);
        start.setText("START LINK BASS");
        start.setOnClickListener(view -> {
            nativeSetManualKeyScale(selectedRootPitchClass, selectedScaleId);
            nativeStartAccompaniment();
            status.append("\n\nAccompaniment armed; following Link timing.");
            updateLinkStatus();
        });

        Button bass = new Button(this);
        bass.setText("BASS");
        bass.setOnClickListener(view -> {
            nativeSetAccompanimentRole(0);
            status.append("\n\nBass role selected; change takes effect at the next bar.");
        });

        Button arpeggio = new Button(this);
        arpeggio.setText("ARPEGGIO");
        arpeggio.setOnClickListener(view -> {
            nativeSetAccompanimentRole(1);
            status.append("\n\nArpeggio role selected; change takes effect at the next bar.");
        });

        Button density = new Button(this);
        density.setText("DENSITY: FULL");
        final int[] densityIndex = {2};
        density.setOnClickListener(view -> {
            densityIndex[0] = (densityIndex[0] + 1) % 3;
            final int selectedDensity = densityIndex[0];
            nativeSetPatternDensity(selectedDensity);
            final String[] labels = {"DENSITY: SPARSE", "DENSITY: NORMAL", "DENSITY: FULL"};
            density.setText(labels[selectedDensity]);
            status.append(
                    "\n\n" + labels[selectedDensity]
                            + " selected; change takes effect at the next bar.");
        });

        Button accent = new Button(this);
        accent.setText("ACCENT: OFF");
        final int[] accentIndex = {0};
        accent.setOnClickListener(view -> {
            accentIndex[0] = (accentIndex[0] + 1) % 3;
            final int selectedAccent = accentIndex[0];
            nativeSetPatternAccent(selectedAccent);
            final String[] labels = {
                    "ACCENT: OFF",
                    "ACCENT: MILD",
                    "ACCENT: STRONG"
            };
            accent.setText(labels[selectedAccent]);
            status.append(
                    "\n\n" + labels[selectedAccent]
                            + " selected; change takes effect at the next bar.");
        });

        Button swing = new Button(this);
        swing.setText("SWING: OFF");
        final int[] swingIndex = {0};
        swing.setOnClickListener(view -> {
            swingIndex[0] = (swingIndex[0] + 1) % 3;
            final int selectedSwing = swingIndex[0];
            nativeSetPatternSwing(selectedSwing);
            final String[] labels = {
                    "SWING: OFF",
                    "SWING: LIGHT",
                    "SWING: FULL"
            };
            swing.setText(labels[selectedSwing]);
            status.append(
                    "\n\n" + labels[selectedSwing]
                            + " selected; change takes effect at the next bar.");
        });

        Button testMidi = new Button(this);
        testMidi.setText("TEST MIDI OUT");
        testMidi.setOnClickListener(view -> {
            final boolean queued = nativeTestMidiNote();
            status.append(
                    queued
                            ? "\n\nDiagnostic C2 note queued."
                            : "\n\nDiagnostic C2 note could not be queued; check MIDI OUT status.");
        });

        Button stop = new Button(this);
        stop.setText("STOP");
        stop.setOnClickListener(view -> {
            nativeStopAccompaniment();
            status.append("\n\nAccompaniment stopped.");
            updateLinkStatus();
        });

        root.addView(
                title,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                status,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1.0f));
        LinearLayout keyScaleRow = new LinearLayout(this);
        keyScaleRow.setOrientation(LinearLayout.HORIZONTAL);
        keyScaleRow.setGravity(Gravity.CENTER);
        keyScaleRow.addView(
                key,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        1.0f));
        keyScaleRow.addView(
                scale,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        1.0f));
        root.addView(
                keyScaleRow,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                linkStatus,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                start,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout roleRow = new LinearLayout(this);
        roleRow.setOrientation(LinearLayout.HORIZONTAL);
        roleRow.setGravity(Gravity.CENTER);

        roleRow.addView(
                bass,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        1.0f));
        roleRow.addView(
                arpeggio,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        1.0f));

        root.addView(
                roleRow,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                density,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                accent,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                swing,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                testMidi,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(
                stop,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        setContentView(root);
        Log.i(TAG, "STARTUP: setContentView complete");

        if (getIntent().getBooleanExtra(RUNTIME_SMOKE_EXTRA, false)) {
            startRuntimeSmoke();
        }

        midiTransport = new AndroidMidiTransport(this, midiListener);
        Log.i(TAG, "STARTUP: AndroidMidiTransport constructed");
        Log.i(TAG, "STARTUP: onCreate complete");
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
        updateLinkStatus();
        mainHandler.removeCallbacks(linkStatusPoll);
        mainHandler.post(linkStatusPoll);
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
        nativeStopAccompaniment();

        if (midiTransport != null) {
            midiTransport.stop();
        }
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        mainHandler.removeCallbacks(linkStatusPoll);
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
        final StringBuilder text = new StringBuilder();
        text.append("\n").append(nativeEngineInfo());
        text.append("\n\nMIDI endpoints discovered: ").append(endpoints.size());

        if (selectedOutput == null) {
            text.append("\nMIDI OUT: no Arturia MicroFreak endpoint selected");
        } else {
            text.append("\nMIDI OUT: ")
                    .append(selectedOutput.displayName())
                    .append(selectedOutput.isUsb() ? " [USB]" : " [non-USB]")
                    .append("\nAndroid device INPUT port selected for send");
        }

        text.append("\n").append(connectionStatus);
        text.append("\nManual key: ")
                .append(KEY_LABELS[selectedRootPitchClass])
                .append(" ")
                .append(SCALE_LABELS[selectedScaleId]);
        status.setText(text.toString());
    }
}
