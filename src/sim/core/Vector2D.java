package sim.core;

import java.util.Objects;

/**
 * Immutable 2D vector / point. Used for positions everywhere so higher-level code never touches
 * raw x/y doubles directly.
 */
public final class Vector2D {

    public final double x;
    public final double y;

    public Vector2D(double x, double y) {
        this.x = x;
        this.y = y;
    }

    public Vector2D plus(Vector2D other) {
        return new Vector2D(x + other.x, y + other.y);
    }

    public Vector2D minus(Vector2D other) {
        return new Vector2D(x - other.x, y - other.y);
    }

    public double dot(Vector2D other) {
        return x * other.x + y * other.y;
    }

    public double norm() {
        return Math.sqrt(x * x + y * y);
    }

    public double distanceTo(Vector2D other) {
        return this.minus(other).norm();
    }

    @Override
    public String toString() {
        return x + " " + y;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Vector2D)) return false;
        Vector2D v = (Vector2D) o;
        return Double.compare(v.x, x) == 0 && Double.compare(v.y, y) == 0;
    }

    @Override
    public int hashCode() {
        return Objects.hash(x, y);
    }
}
