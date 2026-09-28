package com.miguelduval.mozart;

import android.app.AlertDialog;
import android.content.Context;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Properties;

public final class ExperimentalModelLab {
    public interface Listener {
        void onModelSelected(ModelCandidate model);
    }

    public static final class ModelCandidate {
        public final String modelId;
        public final String displayName;
        public final String backendId;
        public final String artifactPath;
        public final String manifestPath;

        private ModelCandidate(
                String modelId,
                String displayName,
                String backendId,
                String artifactPath,
                String manifestPath) {
            this.modelId = modelId;
            this.displayName = displayName;
            this.backendId = backendId;
            this.artifactPath = artifactPath;
            this.manifestPath = manifestPath;
        }
    }

    private final Context context;
    private final Listener listener;

    public ExperimentalModelLab(Context context, Listener listener) {
        this.context = context;
        this.listener = listener;
    }

    public File modelRoot() {
        return context.getDir("experimental-models", Context.MODE_PRIVATE);
    }

    public List<ModelCandidate> discover() {
        final File root = modelRoot();
        final File[] entries = root.listFiles(File::isDirectory);
        if (entries == null || entries.length == 0) {
            return Collections.emptyList();
        }

        final List<ModelCandidate> models = new ArrayList<>();
        for (File directory : entries) {
            final File propertiesFile = new File(directory, "model.properties");
            if (!propertiesFile.isFile()) {
                continue;
            }

            final Properties properties = new Properties();
            try (FileInputStream input = new FileInputStream(propertiesFile)) {
                properties.load(input);
            } catch (IOException ignored) {
                continue;
            }

            final String modelId = properties.getProperty("modelId", "").trim();
            if (modelId.isEmpty()) {
                continue;
            }

            final String displayName = properties.getProperty(
                    "displayName",
                    modelId).trim();
            final String backendId = properties.getProperty(
                    "backendId",
                    "").trim();
            final String artifactName = properties.getProperty(
                    "artifact",
                    "").trim();
            final String manifestName = properties.getProperty(
                    "manifest",
                    "model.manifest").trim();

            final File artifact = artifactName.isEmpty()
                    ? directory
                    : new File(directory, artifactName);
            final File manifest = new File(directory, manifestName);

            models.add(new ModelCandidate(
                    modelId,
                    displayName,
                    backendId,
                    artifact.getAbsolutePath(),
                    manifest.getAbsolutePath()));
        }

        models.sort((first, second) ->
                first.displayName.compareToIgnoreCase(second.displayName));
        return models;
    }

    public void show() {
        final List<ModelCandidate> models = discover();
        if (models.isEmpty()) {
            final TextView message = new TextView(context);
            message.setPadding(48, 32, 48, 32);
            message.setText(
                    "No experimental models installed.\n\n"
                            + "Models are kept outside the APK in:\n"
                            + modelRoot().getAbsolutePath()
                            + "\n\n"
                            + "Each model directory must contain "
                            + "model.properties.\n\n"
                            + "This lab is development-only; model files are "
                            + "never packaged into the commercial artifact.");

            new AlertDialog.Builder(context)
                    .setTitle("EXPERIMENTAL MODEL LAB")
                    .setView(message)
                    .setPositiveButton("OK", null)
                    .show();
            return;
        }

        final LinearLayout list = new LinearLayout(context);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(24, 16, 24, 16);

        for (ModelCandidate model : models) {
            final TextView item = new TextView(context);
            item.setText(
                    model.displayName
                            + "\n"
                            + model.modelId
                            + "\nbackend: "
                            + (model.backendId.isEmpty()
                            ? "unassigned"
                            : model.backendId));
            item.setTextSize(16.0f);
            item.setPadding(24, 24, 24, 24);
            item.setOnClickListener(view -> {
                if (listener != null) {
                    listener.onModelSelected(model);
                }
            });
            list.addView(item);
        }

        new AlertDialog.Builder(context)
                .setTitle("EXPERIMENTAL MODEL LAB")
                .setMessage("Select a private experimental model")
                .setView(list)
                .setNegativeButton("CLOSE", null)
                .show();
    }
}
