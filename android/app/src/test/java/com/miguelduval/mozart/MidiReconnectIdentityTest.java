package com.miguelduval.mozart;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;

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

    @Test
    public void reconnectSelectsUniqueStableCandidate() {
        final var selectionIntent = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var firstCandidate = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var secondCandidate = endpoint(
                92, 0, 1, "Korg", "Korg",
                "Other Synth", "");

        assertEquals(
                0,
                AndroidMidiTransport.findReconnectCandidateIndex(
                        selectionIntent,
                        Arrays.asList(firstCandidate, secondCandidate)));
    }

    @Test
    public void reconnectDoesNotGuessWhenStableIdentityIsAmbiguous() {
        final var selectionIntent = endpoint(
                11, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var firstCandidate = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var secondCandidate = endpoint(
                92, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");

        assertEquals(
                -1,
                AndroidMidiTransport.findReconnectCandidateIndex(
                        selectionIntent,
                        Arrays.asList(firstCandidate, secondCandidate)));
    }

    @Test
    public void reconnectPreservesExactDeviceAndPortBeforeStableFallback() {
        final var selectionIntent = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var exactCandidate = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");
        final var stableCandidate = endpoint(
                92, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");

        assertEquals(
                0,
                AndroidMidiTransport.findReconnectCandidateIndex(
                        selectionIntent,
                        Arrays.asList(exactCandidate, stableCandidate)));
    }

    @Test
    public void reconnectReturnsNoCandidateForNullIntentOrEmptyInventory() {
        final var candidate = endpoint(
                91, 0, 1, "Arturia MicroFreak", "Arturia",
                "MicroFreak", "");

        assertEquals(
                -1,
                AndroidMidiTransport.findReconnectCandidateIndex(
                        null,
                        Collections.singletonList(candidate)));
        assertEquals(
                -1,
                AndroidMidiTransport.findReconnectCandidateIndex(
                        candidate,
                        Collections.emptyList()));
    }
}
