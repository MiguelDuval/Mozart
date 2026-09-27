package com.miguelduval.mozart;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.util.Log;

import java.util.concurrent.atomic.AtomicBoolean;

public final class AndroidAudioKeyInput {
    private static final String TAG = "MozartAudioKey";
    private static final int SAMPLE_RATE = 48_000;
    private static final int FRAME_SAMPLES = 4096;

    private final AtomicBoolean running = new AtomicBoolean(false);
    private AudioRecord recorder;
    private Thread worker;

    public boolean start() {
        if (running.get()) {
            return true;
        }

        final int minimumBuffer =
                AudioRecord.getMinBufferSize(
                        SAMPLE_RATE,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT);
        if (minimumBuffer <= 0) {
            Log.e(TAG, "AudioRecord.getMinBufferSize failed: " + minimumBuffer);
            return false;
        }

        final int bufferBytes =
                Math.max(minimumBuffer, FRAME_SAMPLES * 2 * 2);

        final AudioRecord localRecorder;
        try {
            localRecorder = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferBytes);
        } catch (IllegalArgumentException e) {
            Log.e(TAG, "AudioRecord construction failed", e);
            return false;
        }

        if (localRecorder.getState() != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "AudioRecord not initialized");
            localRecorder.release();
            return false;
        }

        try {
            localRecorder.startRecording();
        } catch (IllegalStateException e) {
            Log.e(TAG, "AudioRecord start failed", e);
            localRecorder.release();
            return false;
        }

        recorder = localRecorder;
        running.set(true);
        worker = new Thread(
                () -> captureLoop(localRecorder),
                "MozartAudioKey");
        worker.start();
        return true;
    }

    public void stop() {
        running.set(false);

        final AudioRecord localRecorder = recorder;
        if (localRecorder != null) {
            try {
                localRecorder.stop();
            } catch (IllegalStateException ignored) {
                // Already stopped/released.
            }
        }

        final Thread localWorker = worker;
        if (localWorker != null && localWorker != Thread.currentThread()) {
            try {
                localWorker.join(500L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        if (localRecorder != null) {
            localRecorder.release();
        }

        recorder = null;
        worker = null;
    }

    public boolean isRunning() {
        return running.get();
    }

    private void captureLoop(AudioRecord localRecorder) {
        final short[] buffer = new short[FRAME_SAMPLES];

        while (running.get()) {
            final int read = localRecorder.read(
                    buffer,
                    0,
                    buffer.length,
                    AudioRecord.READ_BLOCKING);
            if (read < 0) {
                Log.e(TAG, "AudioRecord.read failed: " + read);
                break;
            }
            if (read == buffer.length) {
                nativeProcessAudioFrame(buffer, SAMPLE_RATE);
            }
        }
    }

    private static native void nativeProcessAudioFrame(
            short[] samples,
            int sampleRate);
}
