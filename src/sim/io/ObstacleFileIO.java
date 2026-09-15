package sim.io;

import sim.core.Obstacle;
import sim.core.Vector2D;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Reads/writes the obstacle file - one line per obstacle, no header:
 *
 *   x1 y1 R1
 *   ...
 *   xm ym Rm
 *
 * This file is an external input (built by whoever explores obstacle configurations for point
 * 1.2); this class only reads it back into Obstacle objects, plus a write() used by tests/tools.
 */
public final class ObstacleFileIO {

    private ObstacleFileIO() {}

    public static List<Obstacle> read(Path path) {
        List<Obstacle> obstacles = new ArrayList<>();
        try {
            int id = 0;
            for (String line : Files.readAllLines(path)) {
                String trimmed = line.strip();
                if (trimmed.isEmpty()) continue;
                String[] tokens = trimmed.split("\\s+");
                double x = Double.parseDouble(tokens[0]);
                double y = Double.parseDouble(tokens[1]);
                double r = Double.parseDouble(tokens[2]);
                obstacles.add(new Obstacle(id++, new Vector2D(x, y), r));
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return obstacles;
    }

    public static void write(Path path, List<Obstacle> obstacles) {
        StringBuilder sb = new StringBuilder();
        for (Obstacle o : obstacles) {
            sb.append(fmt(o.getPosition().x)).append(' ')
              .append(fmt(o.getPosition().y)).append(' ')
              .append(fmt(o.getRadius())).append('\n');
        }
        try {
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            Files.writeString(path, sb.toString());
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private static String fmt(double v) {
        return String.format(Locale.US, "%.6f", v);
    }
}
