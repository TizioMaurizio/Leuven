"""
Command Line Interface for Manufacturing Loop Simulator.

Entry point for running the closed-loop two-station manufacturing system.

Usage:
    python -m manufacturing_loop_sim [OPTIONS]

Options:
    --render / --no-render  Enable/disable visualization (default: True)
    --duration FLOAT        Simulation duration in seconds (default: 1000)
    --pallets INT           Number of circulating pallets (default: 12)
    --seed INT              Random seed for reproducibility
    --conveyor-capacity INT Capacity of each conveyor buffer (default: 8)
    --speed FLOAT           Render speed multiplier (default: 1.0)
    --export PATH           Export metrics to CSV file

Examples:
    python -m manufacturing_loop_sim --render
    python -m manufacturing_loop_sim --no-render --duration 10000
    python -m manufacturing_loop_sim --pallets 8 --conveyor-capacity 4
"""

import argparse
import sys
from typing import Optional

from manufacturing_loop_sim.config import SimConfig
from manufacturing_loop_sim.sim.engine import ClosedLoopSimulation
from manufacturing_loop_sim.viz.renderer import LoopRenderer
from manufacturing_loop_sim.metrics import MetricsCollector


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Closed-Loop Manufacturing System Simulator",
        prog="manufacturing_loop_sim"
    )
    
    # Rendering
    parser.add_argument(
        "--render", dest="render", action="store_true",
        help="Enable visualization (default)"
    )
    parser.add_argument(
        "--no-render", dest="render", action="store_false",
        help="Disable visualization"
    )
    parser.set_defaults(render=True)
    
    # Simulation parameters
    parser.add_argument(
        "--duration", type=float, default=1000.0,
        help="Simulation duration in seconds (default: 1000)"
    )
    parser.add_argument(
        "--pallets", type=int, default=12,
        help="Number of circulating pallets (default: 12)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--conveyor-capacity", type=int, default=8,
        help="Capacity of each conveyor buffer (default: 8)"
    )
    
    # Station processing times (triangular distribution)
    parser.add_argument(
        "--s1-time", type=float, nargs=3, metavar=("MIN", "MODE", "MAX"),
        default=[3.0, 5.0, 8.0],
        help="Station 1 processing time (min, mode, max) (default: 3 5 8)"
    )
    parser.add_argument(
        "--s2-time", type=float, nargs=3, metavar=("MIN", "MODE", "MAX"),
        default=[2.0, 3.0, 5.0],
        help="Station 2 processing time (min, mode, max) (default: 2 3 5)"
    )
    
    # Visualization options
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Render speed multiplier (default: 1.0)"
    )
    parser.add_argument(
        "--width", type=int, default=1400,
        help="Window width in pixels (default: 1400)"
    )
    parser.add_argument(
        "--height", type=int, default=900,
        help="Window height in pixels (default: 900)"
    )
    
    # Output
    parser.add_argument(
        "--export", type=str, default=None,
        help="Export metrics to CSV file"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print detailed progress information"
    )
    
    return parser.parse_args()


def create_config(args: argparse.Namespace) -> SimConfig:
    """Create simulation configuration from command line arguments."""
    config = SimConfig(
        duration=args.duration,
        num_pallets=args.pallets,
        conveyor_s1_to_s2_capacity=args.conveyor_capacity,
        conveyor_s2_to_s1_capacity=args.conveyor_capacity,
        s1_time_min=args.s1_time[0],
        s1_time_mode=args.s1_time[1],
        s1_time_max=args.s1_time[2],
        s2_time_min=args.s2_time[0],
        s2_time_mode=args.s2_time[1],
        s2_time_max=args.s2_time[2],
        render_speed=args.speed,
        window_width=args.width,
        window_height=args.height,
    )
    
    if args.seed is not None:
        config.seed = args.seed
    
    return config


def run_headless(config: SimConfig, verbose: bool = False) -> ClosedLoopSimulation:
    """Run simulation without visualization."""
    print("=" * 60)
    print("CLOSED-LOOP MANUFACTURING SYSTEM SIMULATOR")
    print("Running in headless mode (no visualization)")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Duration: {config.duration}s")
    print(f"  Pallets: {config.num_pallets}")
    print(f"  Conveyor Capacity: {config.conveyor_s1_to_s2_capacity}")
    print(f"  S1 Processing Time: Triangular({config.s1_time_min}, {config.s1_time_mode}, {config.s1_time_max})")
    print(f"  S2 Processing Time: Triangular({config.s2_time_min}, {config.s2_time_mode}, {config.s2_time_max})")
    print(f"  Seed: {config.seed}")
    print("\nStarting simulation...")
    
    sim = ClosedLoopSimulation(config)
    sim.initialize()
    
    # Run to completion
    target = config.duration
    step = target / 10
    
    for i in range(10):
        current_target = min((i + 1) * step, target)
        sim.env.run(until=current_target)
        if verbose:
            state = sim.get_state()
            print(f"  Progress: {current_target:.0f}s / {target:.0f}s - "
                  f"Cycles: {state.total_cycles}")
    
    print("\nSimulation complete!")
    return sim


def run_with_visualization(config: SimConfig) -> ClosedLoopSimulation:
    """Run simulation with pygame visualization."""
    print("=" * 60)
    print("CLOSED-LOOP MANUFACTURING SYSTEM SIMULATOR")
    print("Running with visualization")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Duration: {config.duration}s")
    print(f"  Pallets: {config.num_pallets}")
    print(f"  Conveyor Capacity: {config.conveyor_s1_to_s2_capacity}")
    print(f"  S1 Processing Time: Triangular({config.s1_time_min}, {config.s1_time_mode}, {config.s1_time_max})")
    print(f"  S2 Processing Time: Triangular({config.s2_time_min}, {config.s2_time_mode}, {config.s2_time_max})")
    print(f"  Seed: {config.seed}")
    print(f"  Render Speed: {config.render_speed}x")
    print("\nControls:")
    print("  ESC - Quit")
    print("\nStarting...")
    
    sim = ClosedLoopSimulation(config)
    sim.initialize()
    
    renderer = LoopRenderer(config)
    renderer.initialize()
    
    import pygame
    
    try:
        running = True
        
        while running and sim.env.now < config.duration:
            # Step simulation
            time_step = config.render_speed / config.render_fps
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
    
    return sim


def main():
    """Main entry point."""
    args = parse_args()
    config = create_config(args)
    
    try:
        if args.render:
            sim = run_with_visualization(config)
        else:
            sim = run_headless(config, verbose=args.verbose)
        
        # Collect and display metrics
        collector = MetricsCollector(sim)
        metrics = collector.collect()
        collector.print_summary(metrics)
        
        # Export if requested
        if args.export:
            collector.export_csv(args.export, metrics)
        
        return 0
        
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
