package sim.io;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;

/**
 * Writes the goal log: one line per goal, "t_gol N_g", where N_g is the accumulated goal count
 * right after that goal (i.e. the number of "usada" particles at t_gol).
 *
 * This is the minimal output needed to reconstruct Fu(t) = N_g(t)/N and t90 for a run. The
 * trajectory file could give the same information, but it carries one full N-particle block per
 * event - thousands of times more data than the at-most-N lines written here - which makes the
 * configuration sweeps of point 1.2 impractical to run and to parse.
 */
public final class GoalFileIO {

    private GoalFileIO() {}

    /**
     * @param times      goal times, in chronological order
     * @param goalCounts N_g right after each goal, same order and length as {@code times}
     * @param count      how many entries of both arrays are actually filled
     */
    public static void write(Path path, double[] times, int[] goalCounts, int count) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < count; i++) {
            sb.append(String.format(Locale.US, "%.6f", times[i])).append(' ')
              .append(goalCounts[i]).append('\n');
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
}
