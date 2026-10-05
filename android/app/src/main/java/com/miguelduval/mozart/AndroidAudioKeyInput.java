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
    private static final int READ_CHUNK_SAMPLES = 1024;

    private final AtomicBoolean running = new AtomicBoolean(false);
    private final Object lifecycleLock = new Object();
    private AudioRecord recorder;
    private Thread worker;

    public boolean start() {
        synchronized (lifecycleLock) {
            if (running.get()) {
                return true;
            }

            final Thread previousWorker = worker;
            if (previousWorker != null && previousWorker != Thread.currentThread()) {
                joinWorker(previousWorker);
                if (recorder != null) {
                    recorder.release();
                }
                recorder = null;
                worker = null;
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

            final Thread localWorker =
                    new Thread(
                            () -> captureLoop(localRecorder),
                            "MozartAudioKey");

            recorder = localRecorder;
            worker = localWorker;
            running.set(true);

            try {
                localWorker.start();
            } catch (RuntimeException e) {
                running.set(false);
                recorder = null;
                worker = null;
                localRecorder.release();
                Log.e(TAG, "AudioRecord worker start failed", e);
                return false;
            }

            return true;
        }
    }

    public void stop() {
        synchronized (lifecycleLock) {
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
            joinWorker(localWorker);

            if (localRecorder != null) {
                localRecorder.release();
            }

            recorder = null;
            worker = null;
        }
    }

    private static void joinWorker(Thread worker) {
        if (worker == null || worker == Thread.currentThread()) {
            return;
        }

        boolean interrupted = false;
        for (;;) {
            try {
                worker.join();
                break;
            } catch (InterruptedException e) {
                interrupted = true;
            }
        }

        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    public boolean isRunning() {
        return running.get();
    }

    private void captureLoop(AudioRecord localRecorder) {
        final short[] frame = new short[FRAME_SAMPLES];
        final short[] readBuffer = new short[READ_CHUNK_SAMPLES];
        int frameOffset = 0;

        try {
            while (running.get()) {
                final int requested =
                        Math.min(READ_CHUNK_SAMPLES, FRAME_SAMPLES - frameOffset);
                final int read = localRecorder.read(
                        readBuffer,
                        0,
                        requested,
                        AudioRecord.READ_BLOCKING);
                if (read < 0) {
                    Log.e(TAG, "AudioRecord.read failed: " + read);
                    break;
                }
                if (!running.get()) {
                    break;
                }
                if (read == 0) {
                    continue;
                }

                System.arraycopy(readBuffer, 0, frame, frameOffset, read);
                frameOffset += read;

                if (frameOffset == FRAME_SAMPLES) {
                    if (!running.get()) {
                        break;
                    }
                    nativeProcessAudioFrame(frame, SAMPLE_RATE);
                    frameOffset = 0;
                }
            }
        } finally {
            running.set(false);
        }
    }

    private static native void nativeProcessAudioFrame(
            short[] samples,
            int sampleRate);
}
