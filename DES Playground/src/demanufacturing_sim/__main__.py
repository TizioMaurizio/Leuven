"""
DIGITAU Demanufacturing Simulator CLI Entry Point.

Supports two control architectures:
  - holonic: Multi-agent distributed control with product/resource holons
  - orchestrated: Holonic + cognitive orchestrator (LLM-like meta-layer)

Usage:
    python -m demanufacturing_sim [options]

Example:
    python -m demanufacturing_sim --render
    python -m demanufacturing_sim --control holonic --render
    python -m demanufacturing_sim --control orchestrated --fault-scenario robot_down
    python -m demanufacturing_sim --duration 480 --seed 42
    python -m demanufacturing_sim --no-render --export results.csv

CONCEPT MAPPING (from HarbourSim):
- Container → Product (end-of-life battery/component)
- Ship → ProductBatch (incoming stream of products)
- Quay Crane → Processing Station (inspection, dismantling, testing)
- Yard → Buffer (WIP storage)
- Yard Mover → Operator (robot or human-robot collaborative)
- Truck → Exit Vehicle (carries products to reuse/remanufacture/recycle)

HOLONIC EXTENSIONS:
- ProductHolon: Agent for each EoL product with BOM uncertainty model
- ResourceHolon: Agent for each station with health/failure model
- TransportHolon: Agent for AGVs/conveyors
- SystemHolon: Aggregator for system-wide state
- CognitiveOrchestrator: Rule-based brain (LLM-swappable interface)
"""

import argparse
import sys
import time

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.engine import DemanufacturingSimulation
from demanufacturing_sim.metrics import MetricsCollector

# Import holonic components
try:
    from demanufacturing_sim.sim.holonic_engine import (
        HolonicDemanufacturingSimulation, ControlMode
    )
    from demanufacturing_sim.sim.fault_injection import FaultInjector
    HOLONIC_AVAILABLE = True
except ImportError as e:
    HOLONIC_AVAILABLE = False
    HOLONIC_IMPORT_ERROR = str(e)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="demanufacturing_sim",
        description="DIGITAU Battery Demanufacturing Digital Twin Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --render                           # Run with visualization (base mode)
  %(prog)s --control holonic --render         # Holonic multi-agent control
  %(prog)s --control orchestrated --render    # With cognitive orchestrator
  %(prog)s --control holonic --fault-scenario robot_down  # Fault injection
  %(prog)s --duration 480                     # Run for 8 hours (480 minutes)
  %(prog)s --seed 42 --no-render              # Reproducible headless run
  %(prog)s --export results.csv               # Export metrics to CSV

Control Modes:
  base         Default SimPy simulation (no holons)
  holonic      Multi-agent control with product/resource/transport holons
  orchestrated Holonic + cognitive orchestrator (rule-based, LLM-swappable)

Fault Scenarios:
  none                 No faults (default)
  robot_down           Single dismantling station fails
  inspection_noise_high  Inspection sensors degrade
  surge_arrivals       3x arrival rate for 30 minutes
  cascading_failures   Multiple sequential failures
  quality_crisis       Low-quality product surge
  stress_test          Combined faults + surge

Concept Mapping from Harbour Simulation:
  Container  → Product (end-of-life battery)
  Ship       → ProductBatch (incoming product stream)
  Crane      → ProcessingStation (inspection/dismantling/testing)
  Yard       → Buffer (WIP storage area)
  YardMover  → Operator (robot or human)
  Truck      → ExitVehicle (to reuse/remanufacture/recycle)
        """
    )
    
    # Control mode
    parser.add_argument(
        "--control", "-c",
        type=str,
        choices=["base", "holonic", "orchestrated"],
        default="base",
        help="Control architecture: base, holonic, or orchestrated (default: base)"
    )
    
    # Fault injection
    parser.add_argument(
        "--fault-scenario", "-f",
        type=str,
        choices=["none", "robot_down", "inspection_noise_high", "surge_arrivals",
                 "cascading_failures", "quality_crisis", "stress_test"],
        default="none",
        help="Fault scenario to inject (default: none)"
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
    
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        default=False,
        help="Open visualization window maximized/fullscreen"
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


def run_with_render(sim: DemanufacturingSimulation, config: SimConfig, use_holonic: bool = False, fullscreen: bool = False):
    """Run simulation with pygame visualization."""
    if use_holonic:
        try:
            from demanufacturing_sim.viz.holonic_renderer import HolonicFactoryRenderer
            renderer_class = HolonicFactoryRenderer
        except ImportError:
            from demanufacturing_sim.viz.renderer import FactoryRenderer
            renderer_class = FactoryRenderer
            use_holonic = False
            print("Warning: Holonic renderer not available, using base renderer")
    else:
        try:
            from demanufacturing_sim.viz.renderer import FactoryRenderer
            renderer_class = FactoryRenderer
        except ImportError as e:
            print(f"Error: pygame not installed. Install with: pip install pygame")
            print(f"Details: {e}")
            sys.exit(1)
    
    print(f"Starting visualization (speed: {config.render_speed}x)...")
    print("Press ESC or close window to exit")
    
    renderer = renderer_class(config)
    # Apply fullscreen flag if requested
    if fullscreen:
        try:
            renderer.fullscreen = True
        except Exception:
            pass
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
            if use_holonic and hasattr(sim, 'get_enhanced_state'):
                state = sim.get_enhanced_state()
                if hasattr(renderer, 'update_enhanced_state'):
                    renderer.update_enhanced_state(state)
                else:
                    renderer.update_state(state)
            else:
                state = sim.get_state()
                renderer.update_state(state)
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
    
    # Determine control mode
    use_holonic = args.control in ("holonic", "orchestrated")
    
    if use_holonic and not HOLONIC_AVAILABLE:
        print(f"Error: Holonic control not available: {HOLONIC_IMPORT_ERROR}")
        print("Falling back to base simulation")
        use_holonic = False
        args.control = "base"
    
    # Build configuration
    config = build_config(args)
    
    if args.verbose:
        print("Configuration:")
        print(f"  Control Mode: {args.control}")
        print(f"  Fault Scenario: {args.fault_scenario}")
        print(f"  Duration: {config.duration} minutes")
        print(f"  Seed: {config.seed}")
        print(f"  Inspection Stations: {config.num_inspection_stations}")
        print(f"  Dismantling Stations: {config.num_dismantling_stations}")
        print(f"  Testing Stations: {config.num_testing_stations}")
        print(f"  Operators: {config.num_operators}")
        print(f"  Buffer: {config.buffer_width}x{config.buffer_height}")
        print(f"  Render: {render}")
        print()
    
    # Create simulation based on control mode
    if use_holonic:
        control_mode = ControlMode.ORCHESTRATED if args.control == "orchestrated" else ControlMode.HOLONIC
        sim = HolonicDemanufacturingSimulation(
            config=config,
            control_mode=control_mode,
            fault_scenario=args.fault_scenario,
            seed=args.seed
        )
        print(f"Using {args.control.upper()} control architecture")
        if args.fault_scenario != "none":
            print(f"Fault scenario: {args.fault_scenario}")
    else:
        sim = DemanufacturingSimulation(config)
        print("Using BASE simulation engine")
    
    # Run simulation
    if render:
        run_with_render(sim, config, use_holonic=use_holonic, fullscreen=args.fullscreen)
    else:
        run_headless(sim, args.verbose)
    
    # Collect and display metrics
    collector = MetricsCollector(sim)
    metrics = collector.collect()
    
    if not args.quiet:
        collector.print_summary(metrics)
        
        # Print resilience metrics for holonic simulation
        if use_holonic and hasattr(sim, 'get_resilience_metrics'):
            resilience = sim.get_resilience_metrics()
            print("\n--- Resilience Metrics ---")
            for key, value in resilience.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.3f}")
                else:
                    print(f"  {key}: {value}")
    
    # Export if requested
    if args.export:
        collector.export_csv(args.export, metrics)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
