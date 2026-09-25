package com.miguelduval.mozart;

import android.content.Context;
import android.media.midi.MidiDeviceInfo;
import android.media.midi.MidiManager;
import android.os.Handler;
import android.os.Looper;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Android-only MIDI discovery adapter.
 *
 * This class knows Android MIDI classes and port semantics. It exposes only
 * immutable transport-neutral inventory records to the rest of the app.
 */
public final class AndroidMidiTransport {
    public interface Listener {
        void onMidiInventoryChanged(
                List<MidiEndpoint> endpoints,
                MidiEndpoint selectedOutput);
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
            final String manufacturerPart = manufacturer.isEmpty() ? "" : manufacturer + " ";
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
                public void onDeviceStatusChanged(
                        MidiDeviceStatusAdapterPlaceholder ignored) {
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
            publish(Collections.emptyList(), null);
            return;
        }

        midiManager.registerDeviceCallback(deviceCallback, callbackHandler);
        refresh();
    }

    public void stop() {
        if (midiManager != null) {
            midiManager.unregisterDeviceCallback(deviceCallback);
        }
    }

    public void refresh() {
        if (midiManager == null) {
            publish(Collections.emptyList(), null);
            return;
        }

        final MidiDeviceInfo[] devices = midiManager.getDevices();
        final List<MidiEndpoint> endpoints = new ArrayList<>();

        if (devices != null) {
            for (MidiDeviceInfo device : devices) {
                final android.os.Bundle properties = device.getProperties();
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

        publish(endpoints, selected);
    }

    private void publish(List<MidiEndpoint> endpoints, MidiEndpoint selectedOutput) {
        if (listener != null) {
            listener.onMidiInventoryChanged(
                    Collections.unmodifiableList(new ArrayList<>(endpoints)),
                    selectedOutput);
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

    /*
     * The Android framework type used by the callback is intentionally kept
     * out of the listener contract. The actual callback override below is
     * supplied in the companion source once the platform signature is bound.
     */
    private static final class MidiDeviceStatusAdapterPlaceholder {}
}
