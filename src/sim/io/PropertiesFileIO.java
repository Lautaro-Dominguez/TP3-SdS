package sim.io;

import sim.core.Particle;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Reads/writes the per-particle properties file - one line per particle, no header:
 *
 *   m1 r1
 *   ...
 *   mn rn
 *
 * N is never stored explicitly; it is inferred from the line count wherever this file is read.
 */
public final class PropertiesFileIO {

    private PropertiesFileIO() {}

    public static final class Properties {
        public final double[] masses;
        public final double[] radii;

        public Properties(double[] masses, double[] radii) {
            this.masses = masses;
            this.radii = radii;
        }

        public int n() { return masses.length; }
    }

    public static void write(Path path, List<Particle> particles) {
        StringBuilder sb = new StringBuilder();
        for (Particle p : particles) {
            sb.append(fmt(p.getMass())).append(' ').append(fmt(p.getRadius())).append('\n');
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

    public static Properties read(Path path) {
        List<String> lines = readNonEmptyLines(path);
        int n = lines.size();
        double[] masses = new double[n];
        double[] radii = new double[n];
        for (int i = 0; i < n; i++) {
            String[] tokens = lines.get(i).split("\\s+");
            masses[i] = Double.parseDouble(tokens[0]);
            radii[i] = Double.parseDouble(tokens[1]);
        }
        return new Properties(masses, radii);
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
