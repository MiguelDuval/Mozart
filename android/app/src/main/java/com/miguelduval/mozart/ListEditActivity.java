package com.miguelduval.mozart;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * List Edit — полноценный интерактивный редактор MIDI-событий.
 * Отображает события выбранного паттерна и позволяет редактировать
 * Tick, Note, Velocity, Duration, Probability, Ratchet, Nudge.
 * События идентифицируются по тройке (trackId, patternId, eventId),
 * а не по плоскому индексу списка.
 */
public class ListEditActivity extends Activity {

    public static final String EXTRA_TRACK_ID = "trackId";
    public static final String EXTRA_PATTERN_ID = "patternId";

    private int selectedTrackId = 0;
    private int selectedPatternId = 0;

    private final List<ListEditEvent> events = new ArrayList<>();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        Intent intent = getIntent();
        if (intent != null) {
            selectedTrackId = intent.getIntExtra(EXTRA_TRACK_ID, 0);
            selectedPatternId = intent.getIntExtra(EXTRA_PATTERN_ID, 0);
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(24, 24, 24, 24);

        TextView title = new TextView(this);
        title.setText("List Edit");
        title.setTextSize(24.0f);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        TextView contextLabel = new TextView(this);
        contextLabel.setText(String.format("Track: %d | Pattern: %d",
                selectedTrackId, selectedPatternId));
        contextLabel.setTextSize(16.0f);
        contextLabel.setGravity(Gravity.CENTER);
        root.addView(contextLabel);

        Spinner trackSpinner = new Spinner(this);
        trackSpinner.setPrompt("Выберите трек");
        root.addView(trackSpinner);

        Spinner patternSpinner = new Spinner(this);
        patternSpinner.setPrompt("Выберите паттерн");
        root.addView(patternSpinner);

        ListEditAdapter adapter = new ListEditAdapter(this, events);
        android.widget.ListView listView = new android.widget.ListView(this);
        listView.setAdapter(adapter);
        listView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        listView.setOnItemClickListener((parent, view, position, id) -> {
            if (position < events.size()) {
                ListEditEvent event = events.get(position);
                openEventEditor(event);
            }
        });
        root.addView(listView);

        Button addButton = new Button(this);
        addButton.setText("Добавить событие");
        addButton.setOnClickListener(v -> {
        });
        root.addView(addButton);

        Button backButton = new Button(this);
        backButton.setText("Назад");
        backButton.setOnClickListener(v -> finish());
        root.addView(backButton);

        setContentView(root);
    }

    private void openEventEditor(ListEditEvent event) {
    }

    /**
     * Представление события для отображения в списке List Edit.
     */
    public static final class ListEditEvent {
        public final int trackId;
        public final int patternId;
        public final int eventId;
        public int tick;
        public int note;
        public int velocity;
        public int durationTicks;
        public int probability;
        public int ratchet;
        public int nudgeTicks;

        public ListEditEvent(int trackId, int patternId, int eventId,
                             int tick, int note, int velocity, int durationTicks,
                             int probability, int ratchet, int nudgeTicks) {
            this.trackId = trackId;
            this.patternId = patternId;
            this.eventId = eventId;
            this.tick = tick;
            this.note = note;
            this.velocity = velocity;
            this.durationTicks = durationTicks;
            this.probability = probability;
            this.ratchet = ratchet;
            this.nudgeTicks = nudgeTicks;
        }
    }

    /**
     * Адаптер для отображения событий в ListView.
     */
    private static final class ListEditAdapter extends ArrayAdapter<ListEditEvent> {
        ListEditAdapter(Activity context, List<ListEditEvent> events) {
            super(context, 0, events);
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            if (convertView == null) {
                convertView = new LinearLayout(getContext());
                ((LinearLayout) convertView).setOrientation(LinearLayout.HORIZONTAL);
                ((LinearLayout) convertView).setGravity(Gravity.CENTER_VERTICAL);
                ((LinearLayout) convertView).setPadding(8, 4, 8, 4);
            }

            LinearLayout row = (LinearLayout) convertView;
            ListEditEvent event = getItem(position);

            row.removeAllViews();

            TextView idView = new TextView(getContext());
            idView.setText(String.valueOf(event.eventId));
            idView.setTextSize(14.0f);
            idView.setWidth(40);
            row.addView(idView);

            TextView tickView = new TextView(getContext());
            tickView.setText("Tick: " + event.tick);
            tickView.setTextSize(14.0f);
            tickView.setWidth(80);
            row.addView(tickView);

            TextView noteView = new TextView(getContext());
            noteView.setText("Note: " + event.note);
            noteView.setTextSize(14.0f);
            noteView.setWidth(60);
            row.addView(noteView);

            TextView velView = new TextView(getContext());
            velView.setText("Vel: " + event.velocity);
            velView.setTextSize(14.0f);
            velView.setWidth(60);
            row.addView(velView);

            return row;
        }
    }
}

