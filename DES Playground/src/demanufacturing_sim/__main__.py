"""
DIGITAU Demanufacturing Simulator CLI Entry Point.

Usage:
    python -m demanufacturing_sim [options]

Example:
    python -m demanufacturing_sim --render
    python -m demanufacturing_sim --duration 480 --seed 42
    python -m demanufacturing_sim --no-render --export results.csv

CONCEPT MAPPING (from HarbourSim):
- Container → Product (end-of-life battery/component)
- Ship → ProductBatch (incoming stream of products)
- Quay Crane → Processing Station (inspection, dismantling, testing)
- Yard → Buffer (WIP storage)
- Yard Mover → Operator (robot or human-robot collaborative)
- Truck → Exit Vehicle (carries products to reuse/remanufacture/recycle)
"""

import argparse
import sys
import time

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.engine import DemanufacturingSimulation
from demanufacturing_sim.metrics import MetricsCollector


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="demanufacturing_sim",
        description="DIGITAU Battery Demanufacturing Digital Twin Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --render                  # Run with visualization
  %(prog)s --duration 480            # Run for 8 hours (480 minutes)
  %(prog)s --seed 42 --no-render     # Reproducible headless run
  %(prog)s --export results.csv      # Export metrics to CSV

Concept Mapping from Harbour Simulation:
  Container  → Product (end-of-life battery)
  Ship       → ProductBatch (incoming product stream)
  Crane      → ProcessingStation (inspection/dismantling/testing)
  Yard       → Buffer (WIP storage area)
  YardMover  → Operator (robot or human)
  Truck      → ExitVehicle (to reuse/remanufacture/recycle)
        """
    )
    
    # Simulation parameters
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=240.0,
        help="Simulation duration in minutes (default: 240 = 4 hours)"
    )
    
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    
    # Station counts
    parser.add_argument(
        "--inspection-stations",
        type=int,
        default=None,
        help="Number of inspection stations (default: 2)"
    )
    
    parser.add_argument(
        "--dismantling-stations",
        type=int,
        default=None,
        help="Number of dismantling stations (default: 3)"
    )
    
    parser.add_argument(
        "--testing-stations",
        type=int,
        default=None,
        help="Number of testing stations (default: 2)"
    )
    
    # Other resources
    parser.add_argument(
        "--operators",
        type=int,
        default=None,
        help="Number of operators (default: 6)"
    )
    
    parser.add_argument(
        "--exit-gates",
        type=int,
        default=None,
        help="Number of exit gates per category (default: 2)"
    )
    
    parser.add_argument(
        "--buffer-capacity",
        type=int,
        default=None,
        help="Buffer capacity in products (default: 100)"
    )
    
    # Visualization
    parser.add_argument(
        "--render", "-r",
        action="store_true",
        default=False,
        help="Enable pygame visualization"
    )
    
    parser.add_argument(
        "--no-render",
        action="store_true",
        default=False,
        help="Disable visualization (headless mode)"
    )
    
    parser.add_argument(
        "--speed",
        type=float,
        default=60.0,
        help="Visualization speed multiplier (default: 60)"
    )
    
    parser.add_argument(
        "--width",
        type=int,
        default=1400,
        help="Window width in pixels (default: 1400)"
    )
    
    parser.add_argument(
        "--height",
        type=int,
        default=900,
        help="Window height in pixels (default: 900)"
    )
    
    # Output
    parser.add_argument(
        "--export", "-e",
        type=str,
        default=None,
        metavar="FILE",
        help="Export metrics to CSV file"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress summary output"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def build_config(args) -> SimConfig:
    """Build simulation configuration from arguments."""
    config = SimConfig(
        duration=args.duration,
        seed=args.seed,
        render_speed=args.speed,
        window_width=args.width,
        window_height=args.height,
    )
    
    # Override station counts if specified
    if args.inspection_stations is not None:
        config.num_inspection_stations = args.inspection_stations
    if args.dismantling_stations is not None:
        config.num_dismantling_stations = args.dismantling_stations
    if args.testing_stations is not None:
        config.num_testing_stations = args.testing_stations
    if args.operators is not None:
        config.num_operators = args.operators
    if args.exit_gates is not None:
        config.num_reuse_gates = args.exit_gates
        config.num_remanufacture_gates = args.exit_gates
        config.num_recycle_gates = args.exit_gates
    if args.buffer_capacity is not None:
        config.buffer_capacity = args.buffer_capacity
    
    return config


def run_headless(sim: DemanufacturingSimulation, verbose: bool = False):
    """Run simulation without visualization."""
    print(f"Running headless simulation for {sim.config.duration} minutes...")
    start_time = time.time()
    
    sim.run()
    
    elapsed = time.time() - start_time
    print(f"Simulation completed in {elapsed:.2f} seconds (wall clock)")


def run_with_render(sim: DemanufacturingSimulation, config: SimConfig):
    """Run simulation with pygame visualization."""
    try:
        from demanufacturing_sim.viz.renderer import FactoryRenderer
    except ImportError as e:
        print(f"Error: pygame not installed. Install with: pip install pygame")
        print(f"Details: {e}")
        sys.exit(1)
    
    print(f"Starting visualization (speed: {config.render_speed}x)...")
    print("Press ESC or close window to exit")
    
    renderer = FactoryRenderer(config)
    renderer.initialize()
    
    # Initialize simulation processes
    sim.initialize()
    
    # Run until completion or window closed
    import pygame
    
    try:
        running = True
        
        while running and sim.env.now < config.duration:
            # Step simulation
            time_step = config.render_speed / 60.0  # Convert to sim minutes per frame
            target_time = sim.env.now + time_step
            
            if target_time < config.duration:
                try:
                    sim.env.run(until=target_time)
                except Exception as e:
                    print(f"Simulation error: {e}")
                    break
            
            # Update renderer with current state
            state = sim.get_state()
            renderer.update_state(state)
            
            # Render and check for exit
            if not renderer.render():
                running = False
            
            # Cap frame rate
            renderer.tick(config.render_fps)
        
        renderer.close()
        
    except Exception as e:
        print(f"Visualization error: {e}")
        renderer.close()
        raise


def main():
    """Main entry point."""
    args = parse_args()
    
    # Determine render mode
    render = args.render and not args.no_render
    
    # Build configuration
    config = build_config(args)
    
    if args.verbose:
        print("Configuration:")
        print(f"  Duration: {config.duration} minutes")
        print(f"  Seed: {config.seed}")
        print(f"  Inspection Stations: {config.num_inspection_stations}")
        print(f"  Dismantling Stations: {config.num_dismantling_stations}")
        print(f"  Testing Stations: {config.num_testing_stations}")
        print(f"  Operators: {config.num_operators}")
        print(f"  Buffer: {config.buffer_width}x{config.buffer_height}")
        print(f"  Render: {render}")
        print()
    
    # Create simulation
    sim = DemanufacturingSimulation(config)
    
    # Run simulation
    if render:
        run_with_render(sim, config)
    else:
        run_headless(sim, args.verbose)
    
    # Collect and display metrics
    collector = MetricsCollector(sim)
    metrics = collector.collect()
    
    if not args.quiet:
        collector.print_summary(metrics)
    
    # Export if requested
    if args.export:
        collector.export_csv(args.export, metrics)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
