package com.miguelduval.mozart;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.List;

public final class MainActivity extends Activity {
    static {
        System.loadLibrary("mozart");
    }

    private static native String nativeEngineInfo();

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
        status.setText("\n" + nativeEngineInfo() + "\n\nMIDI discovery: waiting...");
        status.setTextSize(16.0f);
        status.setGravity(Gravity.CENTER);

        root.addView(title);
        root.addView(status);

        setContentView(root);

        midiTransport = new AndroidMidiTransport(this, midiListener);
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (midiTransport != null) {
            midiTransport.start();
        }
    }

    @Override
    protected void onStop() {
        if (midiTransport != null) {
            midiTransport.stop();
        }
        super.onStop();
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
        status.setText(text.toString());
    }
}
