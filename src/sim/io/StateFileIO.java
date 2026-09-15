package sim.io;

import sim.core.Particle;
import sim.core.Vector2D;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Reads/writes the trajectory file: one block per saved simulation instant -
 *
 *   t_e
 *   x1 y1 v1 color1 theta1
 *   ...
 *   xn yn vn colorn thetan
 *
 * The header is the actual simulation time t_e (not a sequential index), since the whole point
 * of an event-driven simulation is that events land at irregular real times - later analysis
 * (Fu(t), MSD(t), t90) needs that real value, not "block number". writeInitial creates the file
 * with the t=0 block (what the generator produces); appendBlock extends it with the next saved
 * block (what the simulation engine does after every saveEvery-th accepted collision), so the
 * same file grows in place across both programs.
 */
public final class StateFileIO {

    public static final String COLOR_FRESH = "azul";
    public static final String COLOR_USED = "rojo";

    private StateFileIO() {}

    public static void writeInitial(Path path, List<Particle> particles) {
        write(path, false, 0.0, particles);
    }

    public static void appendBlock(Path path, double t, List<Particle> particles) {
        write(path, true, t, particles);
    }

    private static void write(Path path, boolean append, double t, List<Particle> particles) {
        StringBuilder sb = new StringBuilder();
        sb.append(fmt(t)).append('\n');
        for (Particle p : particles) {
            String color = p.getState() == Particle.State.FRESH ? COLOR_FRESH : COLOR_USED;
            sb.append(fmt(p.getPosition().x)).append(' ')
              .append(fmt(p.getPosition().y)).append(' ')
              .append(fmt(p.speed())).append(' ')
              .append(color).append(' ')
              .append(fmt(p.angle())).append('\n');
        }
        try {
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            if (append) {
                Files.writeString(path, sb.toString(), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } else {
                Files.writeString(path, sb.toString());
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /**
     * Reads the first block (t=0 header + N particle rows) and builds particles using the
     * radius/mass already read from the properties file (same order, 1 line per particle).
     */
    public static List<Particle> readFirstBlock(Path path, double[] radii, double[] masses) {
        List<String> lines = readNonEmptyLines(path);
        int n = radii.length;
        List<Particle> particles = new ArrayList<>(n);
        for (int i = 0; i < n; i++) {
            String[] tokens = lines.get(i + 1).split("\\s+");
            double x = Double.parseDouble(tokens[0]);
            double y = Double.parseDouble(tokens[1]);
            double v = Double.parseDouble(tokens[2]);
            String color = tokens[3];
            double theta = Double.parseDouble(tokens[4]);
            Particle p = new Particle(i, new Vector2D(x, y), v * Math.cos(theta), v * Math.sin(theta),
                radii[i], masses[i]);
            if (color.equals(COLOR_USED)) {
                p.markUsed();
            }
            particles.add(p);
        }
        return particles;
    }

    private static String fmt(double v) {
        return String.format(Locale.US, "%.6f", v);
    }

    private static List<String> readNonEmptyLines(Path path) {
        try {
            List<String> nonEmpty = new ArrayList<>();
            for (String line : Files.readAllLines(path)) {
                String trimmed = line.strip();
                if (!trimmed.isEmpty()) {
                    nonEmpty.add(trimmed);
                }
            }
            return nonEmpty;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
