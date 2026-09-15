package sim.core;

/** A fixed circular obstacle of infinite mass: never moves, never changes stamp. */
public final class Obstacle {

    private final int id;
    private final Vector2D position;
    private final double radius;

    public Obstacle(int id, Vector2D position, double radius) {
        this.id = id;
        this.position = position;
        this.radius = radius;
    }

    public int getId() { return id; }

    public Vector2D getPosition() { return position; }

    public double getRadius() { return radius; }
}
