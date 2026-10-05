import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
JAVA_ROOT = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "miguelduval" / "mozart"


class AndroidLifecycleContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = (JAVA_ROOT / "AndroidAudioKeyInput.java").read_text()
        cls.midi_input = (JAVA_ROOT / "AndroidMidiInput.java").read_text()
        cls.midi_transport = (JAVA_ROOT / "AndroidMidiTransport.java").read_text()
        cls.activity = (JAVA_ROOT / "MainActivity.java").read_text()
        cls.model_lab = (JAVA_ROOT / "ExperimentalModelLab.java").read_text()

    def test_audio_shutdown_owns_worker_and_recorder(self):
        self.assertIn("private final Object lifecycleLock", self.audio)
        self.assertIn("private static void joinWorker", self.audio)
        self.assertIn("worker.join()", self.audio)
        self.assertIn("final Thread previousWorker = worker", self.audio)
        self.assertIn("previousWorker != null && previousWorker != Thread.currentThread()", self.audio)
        self.assertIn("finally {\n            running.set(false);", self.audio)
        self.assertIn("AudioRecord.READ_BLOCKING", self.audio)

        stop_pos = self.audio.index("public void stop()")
        release_pos = self.audio.index("localRecorder.release()", stop_pos)
        join_pos = self.audio.index("joinWorker(localWorker)", stop_pos)
        self.assertLess(join_pos, release_pos)

    def test_audio_interrupt_is_restored_after_worker_join(self):
        helper_pos = self.audio.index("private static void joinWorker")
        helper = self.audio[helper_pos:]
        self.assertIn("catch (InterruptedException e)", helper)
        self.assertIn("interrupted = true", helper)
        self.assertIn("Thread.currentThread().interrupt()", helper)

    def test_midi_input_callbacks_are_session_scoped(self):
        self.assertIn("AtomicLong connectionGeneration", self.midi_input)
        self.assertIn("Object receiverLock", self.midi_input)
        self.assertIn("connectionGeneration.incrementAndGet()", self.midi_input)
        self.assertIn("synchronized (receiverLock)", self.midi_input)
        self.assertIn("connectionGeneration.get() != generation", self.midi_input)
        self.assertIn("listener = null", self.midi_input)

    def test_midi_output_open_callbacks_are_session_scoped(self):
        self.assertIn("AtomicLong connectionGeneration", self.midi_transport)
        self.assertIn("connectionGeneration.incrementAndGet()", self.midi_transport)
        self.assertIn("connectionGeneration.get() != generation", self.midi_transport)
        self.assertIn("!started", self.midi_transport)
        self.assertIn("listener = null", self.midi_transport)

    def test_midi_device_removal_invalidates_output_session(self):
        removal = self.midi_transport[
            self.midi_transport.index("public void onDeviceRemoved")
        :]
        self.assertIn("closeOutputInternal()", removal)
        self.assertIn("requestRefresh()", removal)

    def test_runtime_smoke_callbacks_are_lifecycle_scoped(self):
        tick = self.activity.index("private final Runnable runtimeSmokeTick")
        stop = self.activity.index("private final Runnable runtimeSmokeStop")
        self.assertLess(tick, stop)

        start = self.activity.index("private void startRuntimeSmoke()")
        self.assertIn("removeCallbacks(runtimeSmokeTick)", self.activity[start:])
        self.assertIn("removeCallbacks(runtimeSmokeStop)", self.activity[start:])
        self.assertIn("postDelayed(runtimeSmokeTick, 1000L)", self.activity[start:])
        self.assertIn("postDelayed(runtimeSmokeStop, 3000L)", self.activity[start:])

        on_stop = self.activity.index("protected void onStop()")
        self.assertIn("activityStarted = false;", self.activity[on_stop:])
        self.assertIn("removeCallbacks(runtimeSmokeTick)", self.activity[on_stop:])
        self.assertIn("removeCallbacks(runtimeSmokeStop)", self.activity[on_stop:])
        self.assertLess(
            self.activity.index("activityStarted = false;", on_stop),
            self.activity.index("removeCallbacks(runtimeSmokeTick)", on_stop),
        )

        self.assertIn("if (!activityStarted)", self.activity[tick:stop])
        self.assertIn("if (!activityStarted)", self.activity[stop:start])

        on_destroy = self.activity.index("protected void onDestroy()")
        self.assertIn("removeCallbacks(runtimeSmokeTick)", self.activity[on_destroy:])
        self.assertIn("removeCallbacks(runtimeSmokeStop)", self.activity[on_destroy:])

    def test_midi_ui_status_callbacks_are_session_scoped(self):
        transport_publish = self.midi_transport.index("private void publishOnMain")
        transport_publish_body = self.midi_transport[transport_publish:]
        self.assertIn("final long deliveryGeneration = connectionGeneration.get()", transport_publish_body)
        self.assertIn("if (connectionGeneration.get() != deliveryGeneration)", transport_publish_body)

        input_publish = self.midi_input.index("private void publishStatus")
        input_publish_body = self.midi_input[input_publish:]
        self.assertIn("final long deliveryGeneration = connectionGeneration.get()", input_publish_body)
        self.assertIn("if (connectionGeneration.get() != deliveryGeneration)", input_publish_body)

    def test_midi_async_device_cleanup_is_null_safe(self):
        input_cleanup = self.midi_input[
            self.midi_input.index("private static void safeClose(MidiDevice device)")
        :]
        self.assertIn("if (device == null)", input_cleanup)

    def test_midi_input_open_is_idempotent_for_same_pending_endpoint(self):
        open_internal = self.midi_input[
            self.midi_input.index("private void openInternal")
        :]
        self.assertIn("sameEndpoint(pendingEndpoint, endpoint)", open_internal)
        self.assertIn("if (opening &&", open_internal)

    def test_activity_permission_and_debug_lab_shutdown_contract(self):
        self.assertIn("onRequestPermissionsResult", self.activity)
        self.assertIn("RECORD_AUDIO_REQUEST", self.activity)
        self.assertIn("experimentalModelLab.shutdown()", self.activity)

        self.assertIn("AtomicBoolean active", self.model_lab)
        self.assertIn("public void shutdown()", self.model_lab)
        self.assertIn("active.set(false)", self.model_lab)
        self.assertIn("if (!active.get())", self.model_lab)


if __name__ == "__main__":
    unittest.main()
