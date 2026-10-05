package com.miguelduval.mozart;

import android.content.Context;
import android.media.midi.MidiDevice;
import android.media.midi.MidiDeviceInfo;
import android.media.midi.MidiManager;
import android.media.midi.MidiOutputPort;
import android.media.midi.MidiReceiver;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Android MIDI IN adapter.
 *
 * A MIDI device's OUTPUT port is the source seen by Mozart. Android delivers
 * its raw MIDI byte stream asynchronously to MidiReceiver.onSend(). The native
 * boundary receives the byte fragment together with Android's monotonic
 * timestamp; parsing and buffering happen outside the Android/UI layer.
 *
 * This class deliberately does not choose an input source automatically.
 * Source selection belongs to the device-selection/UI layer so a future
 * controller cannot be confused with the MicroFreak output path.
 */
public final class AndroidMidiInput {
    public interface Listener {
        void onMidiInputStatus(String status);
    }

    private final MidiManager midiManager;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final HandlerThread midiThread =
            new HandlerThread("Mozart-MIDI-IN");
    private final Handler midiHandler;
    private volatile Listener listener;
    private final AtomicLong connectionGeneration = new AtomicLong(0L);
    private final Object receiverLock = new Object();

    private MidiDevice openedDevice;
    private MidiOutputPort openedPort;
    private AndroidMidiTransport.MidiEndpoint openedEndpoint;
    private AndroidMidiTransport.MidiEndpoint pendingEndpoint;
    private MidiReceiver activeReceiver;
    private boolean opening;

    public AndroidMidiInput(Context context, Listener listener) {
        midiManager =
                (MidiManager) context.getSystemService(Context.MIDI_SERVICE);
        this.listener = listener;

        midiThread.start();
        midiHandler = new Handler(midiThread.getLooper());
    }

    /**
     * Opens an explicit Android device OUTPUT port as Mozart's MIDI IN source.
     *
     * The supplied endpoint must have PortInfo.TYPE_OUTPUT because MIDI data
     * flows from that device port into Mozart.
     */
    public void open(AndroidMidiTransport.MidiEndpoint endpoint) {
        if (endpoint == null ||
                !endpoint.isDeviceOutput() ||
                midiManager == null) {
            publishStatus("MIDI IN: invalid source or MIDI service unavailable");
            return;
        }

        midiHandler.post(() -> openInternal(endpoint));
    }

    public void close() {
        midiHandler.post(this::closeInternal);
    }

    public void shutdown() {
        listener = null;
        midiHandler.post(() -> {
            closeInternal();
            midiThread.quitSafely();
        });
    }

    private void openInternal(AndroidMidiTransport.MidiEndpoint endpoint) {
        if (opening &&
                ((openedEndpoint != null &&
                  sameEndpoint(openedEndpoint, endpoint)) ||
                 sameEndpoint(pendingEndpoint, endpoint))) {
            return;
        }

        if (openedEndpoint != null &&
                sameEndpoint(openedEndpoint, endpoint) &&
                openedPort != null) {
            return;
        }

        closeInternal();
        final long generation = connectionGeneration.get();
        opening = true;
        pendingEndpoint = endpoint;
        publishStatus("MIDI IN: opening " + endpoint.displayName() + "...");

        final MidiDeviceInfo[] devices = midiManager.getDevices();
        final MidiDeviceInfo target = findDeviceInfo(devices, endpoint.deviceId);
        if (target == null ||
                target.getOutputPortCount() <= endpoint.portNumber) {
            opening = false;
            pendingEndpoint = null;
            publishStatus("MIDI IN: source endpoint is no longer available");
            return;
        }

        nativeResetMidiInput();

        midiManager.openDevice(
                target,
                device -> {
                    if (connectionGeneration.get() != generation ||
                            !sameRequestedEndpoint(endpoint)) {
                        if (device != null) {
                            safeClose(device);
                        }
                        return;
                    }

                    opening = false;

                    if (device == null) {
                        pendingEndpoint = null;
                        publishStatus("MIDI IN: Android failed to open source device");
                        return;
                    }

                    pendingEndpoint = null;

                    final MidiOutputPort outputPort =
                            device.openOutputPort(endpoint.portNumber);
                    if (outputPort == null) {
                        safeClose(device);
                        publishStatus("MIDI IN: failed to open device OUTPUT port");
                        return;
                    }

                    final MidiReceiver connectionReceiver =
                            createReceiver(generation, portIdFor(endpoint));
                    openedDevice = device;
                    openedPort = outputPort;
                    openedEndpoint = endpoint;
                    activeReceiver = connectionReceiver;

                    try {
                        outputPort.connect(connectionReceiver);
                    } catch (RuntimeException exception) {
                        closeInternal();
                        publishStatus("MIDI IN: failed to connect MidiReceiver");
                        return;
                    }
                    publishStatus(
                            "MIDI IN: connected " + endpoint.displayName());
                },
                midiHandler);
    }

    private MidiReceiver createReceiver(
            final long generation,
            final int portId) {
        return new MidiReceiver() {
            @Override
            public void onSend(
                    byte[] msg,
                    int offset,
                    int count,
                    long timestamp) throws IOException {
                synchronized (receiverLock) {
                    if (connectionGeneration.get() != generation ||
                            msg == null ||
                            count <= 0) {
                        return;
                    }

                    nativeReceiveMidiBytes(
                            msg,
                            offset,
                            count,
                            timestamp,
                            portId);
                }
            }
        };
    }

    private static int portIdFor(
            AndroidMidiTransport.MidiEndpoint endpoint) {
        if (endpoint == null) {
            return 0;
        }

        return ((endpoint.deviceId & 0xFFFF) << 16) |
                (endpoint.portNumber & 0xFFFF);
    }

    private boolean sameRequestedEndpoint(
            AndroidMidiTransport.MidiEndpoint endpoint) {
        return sameEndpoint(pendingEndpoint, endpoint);
    }

    private static boolean sameEndpoint(
            AndroidMidiTransport.MidiEndpoint first,
            AndroidMidiTransport.MidiEndpoint second) {
        return first != null &&
                second != null &&
                first.deviceId == second.deviceId &&
                first.portNumber == second.portNumber;
    }

    private static MidiDeviceInfo findDeviceInfo(
            MidiDeviceInfo[] devices,
            int deviceId) {
        if (devices == null) {
            return null;
        }

        for (MidiDeviceInfo device : devices) {
            if (device.getId() == deviceId) {
                return device;
            }
        }

        return null;
    }

    private void closeInternal() {
        final MidiOutputPort localPort;
        final MidiDevice localDevice;

        synchronized (receiverLock) {
            connectionGeneration.incrementAndGet();
            opening = false;
            pendingEndpoint = null;
            activeReceiver = null;
            nativeResetMidiInput();

            localPort = openedPort;
            localDevice = openedDevice;
            openedPort = null;
            openedDevice = null;
            openedEndpoint = null;
        }

        if (localPort != null) {
            safeClose(localPort);
        }

        if (localDevice != null) {
            safeClose(localDevice);
        }
    }

    private void publishStatus(String status) {
        final long deliveryGeneration = connectionGeneration.get();

        mainHandler.post(() -> {
            if (connectionGeneration.get() != deliveryGeneration) {
                return;
            }

            final Listener currentListener = listener;
            if (currentListener != null) {
                currentListener.onMidiInputStatus(status);
            }
        });
    }

    private static void safeClose(MidiOutputPort outputPort) {
        if (outputPort == null) {
            return;
        }

        try {
            outputPort.close();
        } catch (IOException ignored) {
            // The Android resource is already being released.
        }
    }

    private static void safeClose(MidiDevice device) {
        if (device == null) {
            return;
        }

        try {
            device.close();
        } catch (IOException ignored) {
            // The Android resource is already being released.
        }
    }

    private static native void nativeReceiveMidiBytes(
            byte[] data,
            int offset,
            int count,
            long timestampNanos,
            int portId);

    private static native void nativeResetMidiInput();
}
