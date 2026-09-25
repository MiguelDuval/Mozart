package com.miguelduval.mozart;

import android.content.Context;
import android.media.midi.MidiDevice;
import android.media.midi.MidiDeviceInfo;
import android.media.midi.MidiDeviceStatus;
import android.media.midi.MidiManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Android-only MIDI discovery and device lifecycle adapter.
 *
 * Android owns MidiManager, MidiDeviceInfo and MidiDevice. The rest of the
 * application receives immutable endpoint records and transport state.
 */
public final class AndroidMidiTransport {
    public interface Listener {
        void onMidiInventoryChanged(
                List<MidiEndpoint> endpoints,
                MidiEndpoint selectedOutput,
                String connectionStatus);
    }

    public static final class MidiEndpoint {
        public final int deviceId;
        public final int portNumber;
        public final int portType;
        public final int transportType;
        public final String name;
        public final String manufacturer;
        public final String product;

        MidiEndpoint(
                int deviceId,
                int portNumber,
                int portType,
                int transportType,
                String name,
                String manufacturer,
                String product) {
            this.deviceId = deviceId;
            this.portNumber = portNumber;
            this.portType = portType;
            this.transportType = transportType;
            this.name = name;
            this.manufacturer = manufacturer;
            this.product = product;
        }

        public boolean isDeviceInput() {
            return portType == MidiDeviceInfo.PortInfo.TYPE_INPUT;
        }

        public boolean isUsb() {
            return transportType == MidiDeviceInfo.TYPE_USB;
        }

        public String displayName() {
            final String manufacturerPart =
                    manufacturer.isEmpty() ? "" : manufacturer + " ";
            final String productPart = product.isEmpty() ? name : product;
            final String portPart = "port " + portNumber;
            return manufacturerPart + productPart + " (" + portPart + ")";
        }
    }

    private static final String PREFERRED_MANUFACTURER = "Arturia";
    private static final String PREFERRED_PRODUCT = "MicroFreak";

    private final MidiManager midiManager;
    private final Handler callbackHandler = new Handler(Looper.getMainLooper());
    private final Listener listener;

    private MidiDevice openedDevice;
    private int openedDeviceId = -1;
    private int openedPortNumber = -1;

    private boolean opening;
    private MidiEndpoint pendingEndpoint;

    private final MidiManager.DeviceCallback deviceCallback =
            new MidiManager.DeviceCallback() {
                @Override
                public void onDeviceAdded(MidiDeviceInfo device) {
                    refresh();
                }

                @Override
                public void onDeviceRemoved(MidiDeviceInfo device) {
                    refresh();
                }

                @Override
                public void onDeviceStatusChanged(MidiDeviceStatus status) {
                    refresh();
                }
            };

    public AndroidMidiTransport(Context context, Listener listener) {
        this.midiManager =
                (MidiManager) context.getSystemService(Context.MIDI_SERVICE);
        this.listener = listener;
    }

    public void start() {
        if (midiManager == null) {
            publish(
                    Collections.emptyList(),
                    null,
                    "MIDI service unavailable");
            return;
        }

        midiManager.registerDeviceCallback(deviceCallback, callbackHandler);
        refresh();
    }

    public void stop() {
        if (midiManager != null) {
            midiManager.unregisterDeviceCallback(deviceCallback);
        }
        closeOutput();
    }

    public void refresh() {
        if (midiManager == null) {
            publish(
                    Collections.emptyList(),
                    null,
                    "MIDI service unavailable");
            return;
        }

        final MidiDeviceInfo[] devices = midiManager.getDevices();
        final List<MidiEndpoint> endpoints = new ArrayList<>();

        if (devices != null) {
            for (MidiDeviceInfo device : devices) {
                final Bundle properties = device.getProperties();
                final String name = safeString(
                        properties.getString(MidiDeviceInfo.PROPERTY_NAME));
                final String manufacturer = safeString(
                        properties.getString(MidiDeviceInfo.PROPERTY_MANUFACTURER));
                final String product = safeString(
                        properties.getString(MidiDeviceInfo.PROPERTY_PRODUCT));

                for (MidiDeviceInfo.PortInfo port : device.getPorts()) {
                    endpoints.add(new MidiEndpoint(
                            device.getId(),
                            port.getPortNumber(),
                            port.getType(),
                            device.getType(),
                            name,
                            manufacturer,
                            product));
                }
            }
        }

        final int[] deviceIds = new int[endpoints.size()];
        final int[] portNumbers = new int[endpoints.size()];
        final int[] portTypes = new int[endpoints.size()];
        final int[] transportTypes = new int[endpoints.size()];
        final String[] names = new String[endpoints.size()];
        final String[] manufacturers = new String[endpoints.size()];
        final String[] products = new String[endpoints.size()];

        for (int i = 0; i < endpoints.size(); ++i) {
            final MidiEndpoint endpoint = endpoints.get(i);
            deviceIds[i] = endpoint.deviceId;
            portNumbers[i] = endpoint.portNumber;
            portTypes[i] = endpoint.portType;
            transportTypes[i] = endpoint.transportType;
            names[i] = endpoint.name;
            manufacturers[i] = endpoint.manufacturer;
            products[i] = endpoint.product;
        }

        final int selectedIndex = nativeSelectPreferredMidiOutput(
                deviceIds,
                portNumbers,
                portTypes,
                transportTypes,
                names,
                manufacturers,
                products);

        final MidiEndpoint selected =
                selectedIndex >= 0 && selectedIndex < endpoints.size()
                        ? endpoints.get(selectedIndex)
                        : null;

        if (selected == null) {
            pendingEndpoint = null;
            closeOutput();
            publish(
                    endpoints,
                    null,
                    "MIDI OUT: no Arturia MicroFreak USB endpoint selected");
            return;
        }

        if (!selected.isDeviceInput()) {
            pendingEndpoint = null;
            closeOutput();
            publish(
                    endpoints,
                    selected,
                    "MIDI OUT: selected endpoint has wrong port direction");
            return;
        }

        synchronizeOutput(devices, selected);

        final boolean sameOpenEndpoint =
                openedDeviceId == selected.deviceId &&
                openedPortNumber == selected.portNumber &&
                nativeIsMidiOutputOpen();

        final String status;
        if (sameOpenEndpoint) {
            status = "connected via AMidi";
        } else if (opening && samePendingEndpoint(selected)) {
            status = "opening AMidi endpoint...";
        } else {
            status = Build.VERSION.SDK_INT >= 29
                    ? "selected USB endpoint; opening AMidi..."
                    : "selected USB endpoint; AMidi requires Android 10/API 29";
        }

        publish(endpoints, selected, status);
    }

    /**
     * Sends one already validated MIDI 1.0 short message through the native
     * transport boundary. The native AMidi write may block, so the scheduler
     * must call this from its dedicated MIDI transport/send context rather
     * than an audio callback.
     *
     * @return transport status code defined by mozart::midi::MidiTransportStatus.
     */
    public int sendShortMessage(
            int status,
            int data1,
            int data2,
            int size,
            long timestampNanos) {
        return nativeSendShortMessage(
                status,
                data1,
                data2,
                size,
                timestampNanos);
    }

    private void synchronizeOutput(
            MidiDeviceInfo[] devices,
            MidiEndpoint selected) {
        if (Build.VERSION.SDK_INT < 29) {
            pendingEndpoint = selected;
            return;
        }

        if (openedDeviceId == selected.deviceId &&
                openedPortNumber == selected.portNumber &&
                nativeIsMidiOutputOpen()) {
            return;
        }

        if (opening && samePendingEndpoint(selected)) {
            return;
        }

        final MidiDeviceInfo target = findDeviceInfo(devices, selected.deviceId);
        if (target == null || target.getInputPortCount() <= selected.portNumber) {
            pendingEndpoint = null;
            closeOutput();
            return;
        }

        pendingEndpoint = selected;
        closeOutput();

        opening = true;

        midiManager.openDevice(
                target,
                device -> {
                    opening = false;

                    if (device == null) {
                        pendingEndpoint = null;
                        publish(
                                Collections.emptyList(),
                                null,
                                "MIDI OUT: Android failed to open MicroFreak device");
                        return;
                    }

                    if (!samePendingEndpoint(selected)) {
                        safeClose(device);
                        return;
                    }

                    final int nativeStatus =
                            nativeOpenMidiOutputDevice(device, selected.portNumber);

                    if (nativeStatus != 0) {
                        safeClose(device);
                        pendingEndpoint = null;
                        publish(
                                Collections.emptyList(),
                                selected,
                                "MIDI OUT: AMidi open failed, status=" +
                                        nativeStatus);
                        return;
                    }

                    openedDevice = device;
                    openedDeviceId = selected.deviceId;
                    openedPortNumber = selected.portNumber;

                    publish(
                            Collections.emptyList(),
                            selected,
                            "connected via AMidi");
                },
                callbackHandler);
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

    private boolean samePendingEndpoint(MidiEndpoint endpoint) {
        return pendingEndpoint != null &&
                pendingEndpoint.deviceId == endpoint.deviceId &&
                pendingEndpoint.portNumber == endpoint.portNumber;
    }

    private boolean nativeIsMidiOutputOpen() {
        return nativeIsMidiOutputOpenInternal();
    }

    private void closeOutput() {
        opening = false;
        pendingEndpoint = null;
        nativeCloseMidiOutputDevice();

        if (openedDevice != null) {
            safeClose(openedDevice);
            openedDevice = null;
        }

        openedDeviceId = -1;
        openedPortNumber = -1;
    }

    private void publish(
            List<MidiEndpoint> endpoints,
            MidiEndpoint selectedOutput,
            String connectionStatus) {
        if (listener != null) {
            listener.onMidiInventoryChanged(
                    Collections.unmodifiableList(new ArrayList<>(endpoints)),
                    selectedOutput,
                    connectionStatus);
        }
    }

    private static void safeClose(MidiDevice device) {
        try {
            device.close();
        } catch (IOException ignored) {
            // Nothing else can be done for a device that is already being closed.
        }
    }

    private static String safeString(String value) {
        return value == null ? "" : value;
    }

    private static native int nativeSelectPreferredMidiOutput(
            int[] deviceIds,
            int[] portNumbers,
            int[] portTypes,
            int[] transportTypes,
            String[] names,
            String[] manufacturers,
            String[] products);

    private static native int nativeOpenMidiOutputDevice(
            MidiDevice midiDevice,
            int portNumber);

    private static native void nativeCloseMidiOutputDevice();

    private static native boolean nativeIsMidiOutputOpenInternal();

    private static native int nativeSendShortMessage(
            int status,
            int data1,
            int data2,
            int size,
            long timestampNanos);
}
