package com.miguelduval.mozart;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    static {
        System.loadLibrary("mozart");
    }

    private static native String nativeEngineInfo();

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

        TextView status = new TextView(this);
        status.setText("\n" + nativeEngineInfo());
        status.setTextSize(16.0f);
        status.setGravity(Gravity.CENTER);

        root.addView(title);
        root.addView(status);

        setContentView(root);
    }
}
