package sim.generation;

import java.util.ArrayList;
import java.util.List;

/**
 * Bins circles (particles already placed, plus the fixed obstacles) into a uniform grid over the
 * [0,L] x [0,W] domain, sized so any circle that could possibly overlap a candidate position
 * falls in the Moore neighborhood (3x3 block) of the candidate's own cell. Lets
 * {@link ParticlePlacer} check overlap against only nearby occupants instead of every one placed
 * so far.
 */
final class SpatialHashGrid {

    static final class Circle {
        final double x, y, radius;
        Circle(double x, double y, double radius) {
            this.x = x;
            this.y = y;
            this.radius = radius;
        }
    }

    private final double cellSize;
    private final int cols;
    private final int rows;
    private final List<Circle>[][] cells;

    @SuppressWarnings("unchecked")
    SpatialHashGrid(double l, double w, double cellSize) {
        this.cellSize = cellSize;
        this.cols = Math.max(1, (int) Math.ceil(l / cellSize));
        this.rows = Math.max(1, (int) Math.ceil(w / cellSize));
        this.cells = new List[cols][rows];
        for (int i = 0; i < cols; i++) {
            for (int j = 0; j < rows; j++) {
                cells[i][j] = new ArrayList<>();
            }
        }
    }

    void insert(double x, double y, double radius) {
        cells[colOf(x)][rowOf(y)].add(new Circle(x, y, radius));
    }

    boolean overlaps(double x, double y, double radius) {
        int cx = colOf(x);
        int cy = rowOf(y);
        for (int i = Math.max(0, cx - 1); i <= Math.min(cols - 1, cx + 1); i++) {
            for (int j = Math.max(0, cy - 1); j <= Math.min(rows - 1, cy + 1); j++) {
                for (Circle c : cells[i][j]) {
                    double dx = x - c.x;
                    double dy = y - c.y;
                    double minDist = radius + c.radius;
                    if (dx * dx + dy * dy < minDist * minDist) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    private int colOf(double x) {
        return Math.min(cols - 1, Math.max(0, (int) (x / cellSize)));
    }

    private int rowOf(double y) {
        return Math.min(rows - 1, Math.max(0, (int) (y / cellSize)));
    }
}
