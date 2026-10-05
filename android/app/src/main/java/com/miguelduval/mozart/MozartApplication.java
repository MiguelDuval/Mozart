package com.miguelduval.mozart;

import android.app.Application;
import android.content.Context;
import android.util.Log;

public final class MozartApplication extends Application {
    private static final String TAG = "MozartStartup";

    @Override
    protected void attachBaseContext(Context base) {
        Log.i(TAG, "STARTUP: Application attachBaseContext begin");
        super.attachBaseContext(base);
        Log.i(TAG, "STARTUP: Application attachBaseContext complete");
    }

    @Override
    public void onCreate() {
        Log.i(TAG, "STARTUP: Application onCreate begin");
        super.onCreate();
        Log.i(TAG, "STARTUP: Application onCreate complete");
    }
}
