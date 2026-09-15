package sim.app;

import sim.core.Obstacle;
import sim.core.Particle;
import sim.generation.ParticlePlacer;
import sim.io.ObstacleFileIO;
import sim.io.PropertiesFileIO;
import sim.io.StateFileIO;

import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Generates the initial state for the billar-metegol simulation: N non-overlapping fresh
 * particles at random positions with random directions and fixed speed v0, plus the per-particle
 * mass/radius file that {@link SimulateMain} reads alongside it.
 *
 * Usage:
 *   java -cp out sim.app.GenerateMain --N 100 [--L 1.20] [--W 0.68] [--r 0.0175] [--m 0.025]
 *       [--v0 1.0] [--obstacles obstacles.txt] [--seed 42]
 *       [--outState output/particles.txt] [--outProps output/properties.txt]
 */
public final class GenerateMain {

    public static void main(String[] args) {
        Map<String, String> flags = parseFlags(args);

        String nStr = flags.get("N");
        if (nStr == null) {
            throw new IllegalArgumentException("--N is required");
        }
        int n = Integer.parseInt(nStr);
        double l = Double.parseDouble(flags.getOrDefault("L", "1.20"));
        double w = Double.parseDouble(flags.getOrDefault("W", "0.68"));
        double r = Double.parseDouble(flags.getOrDefault("r", "0.0175"));
        double m = Double.parseDouble(flags.getOrDefault("m", "0.025"));
        double v0 = Double.parseDouble(flags.getOrDefault("v0", "1.0"));
        long seed = Long.parseLong(flags.getOrDefault("seed", String.valueOf(System.nanoTime())));
        Path outState = Path.of(flags.getOrDefault("outState", "output/particles.txt"));
        Path outProps = Path.of(flags.getOrDefault("outProps", "output/properties.txt"));

        List<Obstacle> obstacles = Collections.emptyList();
        String obstaclesFlag = flags.get("obstacles");
        if (obstaclesFlag != null) {
            obstacles = ObstacleFileIO.read(Path.of(obstaclesFlag));
        }

        Random rng = new Random(seed);
        List<Particle> particles = ParticlePlacer.place(l, w, n, r, m, v0, obstacles, rng);

        StateFileIO.writeInitial(outState, particles);
        PropertiesFileIO.write(outProps, particles);

        System.out.printf(
            "Generated %d particles (L=%.4f, W=%.4f, r=%.4f, m=%.4f, v0=%.4f, obstacles=%d, seed=%d) -> %s, %s%n",
            n, l, w, r, m, v0, obstacles.size(), seed, outState, outProps);
    }

    private static Map<String, String> parseFlags(String[] args) {
        Map<String, String> raw = new HashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) {
            String key = args[i].startsWith("--") ? args[i].substring(2) : args[i];
            raw.put(key, args[i + 1]);
        }
        return raw;
    }
}
