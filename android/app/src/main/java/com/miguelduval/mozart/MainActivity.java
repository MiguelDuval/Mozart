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
    static {
        Log.i(TAG, "STARTUP: loadLibrary begin");
        System.loadLibrary("mozart");
        Log.i(TAG, "STARTUP: loadLibrary complete");
    }

    private static native String nativeEngineInfo();
    private static native void nativeStartAccompaniment();
    private static native void nativeStopAccompaniment();
    private static native boolean nativeTestMidiNote();
    private static native void nativeSetManualKeyScale(
            int rootPitchClass,
            int scaleId);

    private TextView status;
    private AndroidMidiTransport midiTransport;

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
                + "\nManual key: F# minor"
                + "\nLink accompanist: stopped");
        status.setTextSize(16.0f);
        status.setGravity(Gravity.CENTER);

        Button start = new Button(this);
        start.setText("START LINK BASS");
        start.setOnClickListener(view -> {
            nativeSetManualKeyScale(6, 1);
            nativeStartAccompaniment();
            status.append("\n\nAccompaniment armed; following Link timing.");
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
        root.addView(
                start,
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

        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            nativeStopAccompaniment();
            Log.i(TAG, "RUNTIME: Android smoke stop complete");
        }, 3000L);
    }

    @Override
    protected void onStart() {
        Log.i(TAG, "STARTUP: onStart begin");
        super.onStart();
        if (midiTransport != null) {
            Log.i(TAG, "STARTUP: midiTransport.start posting");
            midiTransport.start();
        }
        Log.i(TAG, "STARTUP: onStart complete");
    }

    @Override
    protected void onStop() {
        nativeStopAccompaniment();

        if (midiTransport != null) {
            midiTransport.stop();
        }
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        if (midiTransport != null) {
            midiTransport.shutdown();
        }
        super.onDestroy();
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
        text.append("\nManual key: F# minor");
        status.setText(text.toString());
    }
}
