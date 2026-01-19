"""
Main entry point for HarbourSim.

Provides CLI interface with render/headless modes and parameter configuration.
"""

import argparse
import sys
import time
import threading
from pathlib import Path

from harbour_sim.config import SimConfig
from harbour_sim.sim.engine import HarbourSimulation
from harbour_sim.sim.policies import PolicyManager
from harbour_sim.metrics import MetricsCollector
from harbour_sim.viz.renderer import HarbourRenderer


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="harbour_sim",
        description="Container Harbour Discrete Event Simulation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Mode
    parser.add_argument(
        "--render", "-r",
        action="store_true",
        default=True,
        help="Enable 2D visualization (default)"
    )
    parser.add_argument(
        "--no-render", "-n",
        action="store_true",
        help="Run headless without visualization"
    )
    
    # Simulation parameters
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=480.0,
        help="Simulation duration in minutes"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=10.0,
        help="Simulation speed multiplier (for render mode)"
    )
    
    # Resource parameters
    parser.add_argument(
        "--berths",
        type=int,
        default=3,
        help="Number of ship berths"
    )
    parser.add_argument(
        "--cranes",
        type=int,
        default=4,
        help="Number of quay cranes"
    )
    parser.add_argument(
        "--gates",
        type=int,
        default=2,
        help="Number of truck gates"
    )
    
    # Yard parameters
    parser.add_argument(
        "--yard-width",
        type=int,
        default=20,
        help="Yard width (bays)"
    )
    parser.add_argument(
        "--yard-height",
        type=int,
        default=10,
        help="Yard height (rows)"
    )
    parser.add_argument(
        "--max-stack",
        type=int,
        default=4,
        help="Maximum container stack height"
    )
    
    # Arrival rates
    parser.add_argument(
        "--ship-arrival",
        type=float,
        default=60.0,
        help="Mean ship interarrival time (minutes)"
    )
    parser.add_argument(
        "--truck-arrival",
        type=float,
        default=5.0,
        help="Mean truck interarrival time (minutes)"
    )
    
    # Output
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="results.csv",
        help="Output CSV file for results"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Load configuration from YAML file"
    )
    parser.add_argument(
        "--save-config",
        type=str,
        help="Save current configuration to YAML file"
    )
    
    return parser.parse_args()


def create_config(args) -> SimConfig:
    """Create configuration from arguments."""
    if args.config:
        config = SimConfig.from_yaml(args.config)
    else:
        config = SimConfig()
    
    # Override with command line arguments
    config.seed = args.seed
    config.duration = args.duration
    config.render_speed = args.speed
    config.num_berths = args.berths
    config.num_quay_cranes = args.cranes
    config.num_truck_gates = args.gates
    config.yard_width = args.yard_width
    config.yard_height = args.yard_height
    config.yard_max_stack_height = args.max_stack
    config.ship_interarrival_mean = args.ship_arrival
    config.truck_interarrival_mean = args.truck_arrival
    config.results_file = args.output
    config.render_enabled = not args.no_render
    
    return config


def run_headless(config: SimConfig):
    """Run simulation without visualization."""
    print("=" * 60)
    print("HARBOUR SIMULATION - Headless Mode")
    print("=" * 60)
    print(f"Duration: {config.duration} minutes")
    print(f"Seed: {config.seed}")
    print(f"Berths: {config.num_berths}, Cranes: {config.num_quay_cranes}")
    print(f"Yard: {config.yard_width}x{config.yard_height}x{config.yard_max_stack_height}")
    print("=" * 60)
    print("\nRunning simulation...")
    
    # Create and run simulation
    sim = HarbourSimulation(config=config, seed=config.seed)
    
    start_time = time.time()
    
    # Progress callback
    last_progress = 0
    def progress_callback(sim_time, state):
        nonlocal last_progress
        progress = int(sim_time / config.duration * 100)
        if progress >= last_progress + 10:
            print(f"  Progress: {progress}% (time={sim_time:.1f})")
            last_progress = progress
    
    sim.run(duration=config.duration, step_callback=progress_callback)
    
    elapsed = time.time() - start_time
    print(f"\nSimulation completed in {elapsed:.2f} seconds")
    
    # Collect and print metrics
    collector = MetricsCollector(sim)
    metrics = collector.collect()
    collector.print_summary(metrics)
    
    # Export to CSV
    collector.export_csv(config.results_file, metrics)
    
    return metrics


def run_with_render(config: SimConfig):
    """Run simulation with 2D visualization."""
    print("=" * 60)
    print("HARBOUR SIMULATION - Visual Mode")
    print("=" * 60)
    print(f"Duration: {config.duration} minutes")
    print(f"Speed: {config.render_speed}x")
    print(f"Press ESC to exit")
    print("=" * 60)
    
    # Create simulation
    sim = HarbourSimulation(config=config, seed=config.seed)
    
    # Create renderer
    renderer = HarbourRenderer(config)
    renderer.initialize()
    
    # Start main processes
    sim.env.process(sim.ship_arrival_process())
    sim.env.process(sim.truck_arrival_process())
    
    running = True
    sim_time = 0.0
    real_time_step = 1.0 / config.render_fps  # Time between frames
    sim_time_step = real_time_step * config.render_speed  # Sim time per frame
    
    try:
        while running and sim_time < config.duration:
            # Advance simulation
            try:
                target_time = min(sim_time + sim_time_step, config.duration)
                sim.env.run(until=target_time)
                sim_time = sim.env.now
                sim._update_state()
            except Exception as e:
                print(f"Simulation error: {e}")
                break
            
            # Update renderer state
            renderer.update_state(sim.state)
            
            # Render frame
            if not renderer.render():
                running = False
                break
            
            # Frame rate limiting
            renderer.tick(config.render_fps)
    
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    
    finally:
        renderer.close()
    
    # Collect and print metrics
    print("\n")
    collector = MetricsCollector(sim)
    metrics = collector.collect()
    collector.print_summary(metrics)
    
    # Export to CSV
    collector.export_csv(config.results_file, metrics)
    
    return metrics


def main():
    """Main entry point."""
    args = parse_args()
    config = create_config(args)
    
    # Save config if requested
    if args.save_config:
        config.to_yaml(args.save_config)
        print(f"Configuration saved to {args.save_config}")
    
    # Run simulation
    if config.render_enabled:
        run_with_render(config)
    else:
        run_headless(config)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
