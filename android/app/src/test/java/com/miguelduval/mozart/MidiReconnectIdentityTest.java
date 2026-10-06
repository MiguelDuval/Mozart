package com.miguelduval.mozart;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class MidiReconnectIdentityTest {
    private static AndroidMidiTransport.MidiEndpoint endpoint(
            int deviceId,
            int portNumber,
            int transportType,
            String name,
            String manufacturer,
            String product,
            String serialNumber) {
        return new AndroidMidiTransport.MidiEndpoint(
                deviceId,
                portNumber,
                2,
                transportType,
                name,
                manufacturer,
                product,
                serialNumber);
    }

    @Test
    public void serialNumberSurvivesChangingAndroidDeviceId() {
        final var before = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-42");
        final var after = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-42");

        assertTrue(AndroidMidiTransport.sameStableEndpoint(before, after));
    }

    @Test
    public void metadataFallbackMatchesWhenSerialIsUnavailable() {
        final var before = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var after = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");

        assertTrue(AndroidMidiTransport.sameStableEndpoint(before, after));
    }

    @Test
    public void differentSerialDoesNotMatch() {
        final var before = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-A");
        final var after = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-B");

        assertFalse(AndroidMidiTransport.sameStableEndpoint(before, after));
    }

    @Test
    public void differentPortDoesNotMatch() {
        final var before = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-42");
        final var after = endpoint(
                91, 1, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "SERIAL-42");

        assertFalse(AndroidMidiTransport.sameStableEndpoint(before, after));
    }
}
