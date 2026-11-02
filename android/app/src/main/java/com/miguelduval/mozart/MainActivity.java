package com.miguelduval.mozart;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    static {
        System.loadLibrary("mozart");
    }

    private static native String nativeEngineInfo();

    private boolean engineInfoVisible = true;
    private MpcUiState.DataDialFocus dataDialFocus = MpcUiState.DataDialFocus.LEVEL;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(48, 48, 48, 48);

        TextView title = new TextView(this);
        title.setText("MOZART");
        title.setTextSize(32.0f);
        title.setGravity(Gravity.CENTER);

        TextView version = new TextView(this);
        version.setText("v0.1.0-foundation");
        version.setTextSize(14.0f);
        version.setGravity(Gravity.CENTER);

        // Channel mixer view — demonstrates explicit DataDialFocus -> ControlFocus mapping
        MpcChannelMixerView channelMixerView = new MpcChannelMixerView(this);
        channelMixerView.setControlFocus(
                MpcChannelMixerView.fromDataDialFocus(dataDialFocus));

        TextView focusLabel = new TextView(this);
        focusLabel.setText("Data Dial Focus: " + dataDialFocus);
        focusLabel.setTextSize(14.0f);
        focusLabel.setGravity(Gravity.CENTER);

        // PANEL_2 color token from unified MpcStyle — single source of visual tokens
        TextView panelToken = new TextView(this);
        panelToken.setText("Panel token: PANEL_2 = #2A2A2A");
        panelToken.setTextSize(12.0f);
        panelToken.setGravity(Gravity.CENTER);
        panelToken.setTextColor(MpcStyle.TEXT_SECONDARY);

        // Touch Strip mode label — single implementation via TouchStripHelper
        TextView touchLabel = new TextView(this);
        touchLabel.setText("Touch Strip: " + TouchStripHelper.touchStripModeLabel(
                MpcStyle.TOUCH_STRIP_MODE_LEVEL));
        touchLabel.setTextSize(14.0f);
        touchLabel.setGravity(Gravity.CENTER);

        TextView status = new TextView(this);
        status.setText("\n" + nativeEngineInfo());
        status.setTextSize(16.0f);
        status.setGravity(Gravity.CENTER);
        status.setId(View.generateViewId());

        Button toggle = new Button(this);
        toggle.setText("Toggle Info");
        toggle.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                engineInfoVisible = !engineInfoVisible;
                status.setText(engineInfoVisible ? "\n" + nativeEngineInfo() : "\nInfo hidden");
            }
        });

        root.addView(title);
        root.addView(version);
        root.addView(focusLabel);
        root.addView(panelToken);
        root.addView(touchLabel);
        root.addView(channelMixerView);
        root.addView(status);
        root.addView(toggle);

        setContentView(root);
    }
}
