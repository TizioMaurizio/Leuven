"""
io/mediator_api.py

Flask-based REST API for cognitive mediation what-if queries.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
It provides read-only access to twin state and what-if query capabilities.
No commands are sent back to mock hardware.
"""

from flask import Flask, jsonify, request
from typing import Optional
import threading

from core.twin_engine import TwinEngine


class MediatorAPI:
    """
    REST API for cognitive mediation queries.
    
    Provides:
    - State inspection endpoints
    - What-if query endpoints for decision support
    - Statistics and monitoring endpoints
    
    ARCHITECTURAL CONSTRAINT:
    - Read-only access to twin state
    - Never sends commands to mock hardware
    """
    
    def __init__(self, twin: TwinEngine, host: str = "0.0.0.0"):
        """
        Initialize the mediator API.
        
        Args:
            twin: TwinEngine to query
            host: Host to bind to
        """
        self.twin = twin
        self.host = host
        self.app = Flask(__name__)
        self._thread: Optional[threading.Thread] = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Configure Flask routes."""
        
        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint."""
            return jsonify({"status": "healthy", "service": "mediator_api"})
        
        # ==================== State Inspection ====================
        
        @self.app.route("/api/products", methods=["GET"])
        def get_products():
            """Get all product holons."""
            products = self.twin.get_all_products()
            return jsonify({
                "count": len(products),
                "products": [p.to_dict() for p in products]
            })
        
        @self.app.route("/api/products/<holon_id>", methods=["GET"])
        def get_product(holon_id: str):
            """Get a specific product holon."""
            product = self.twin.get_product(holon_id)
            if product:
                return jsonify(product.to_dict())
            return jsonify({"error": f"Product {holon_id} not found"}), 404
        
        @self.app.route("/api/products/state/<state>", methods=["GET"])
        def get_products_by_state(state: str):
            """Get products filtered by state."""
            from holons.product_holon import ProductState
            try:
                product_state = ProductState(state.upper())
                products = self.twin.get_products_by_state(product_state)
                return jsonify({
                    "state": state,
                    "count": len(products),
                    "products": [p.to_dict() for p in products]
                })
            except ValueError:
                valid_states = [s.value for s in ProductState]
                return jsonify({
                    "error": f"Invalid state: {state}",
                    "valid_states": valid_states
                }), 400
        
        @self.app.route("/api/products/interventions", methods=["GET"])
        def get_interventions():
            """Get products needing human intervention."""
            products = self.twin.get_products_needing_intervention()
            return jsonify({
                "count": len(products),
                "products": [p.to_dict() for p in products]
            })
        
        @self.app.route("/api/robots", methods=["GET"])
        def get_robots():
            """Get all robot holons."""
            robots = self.twin.get_all_robots()
            return jsonify({
                "count": len(robots),
                "robots": [r.to_dict() for r in robots]
            })
        
        @self.app.route("/api/robots/<holon_id>", methods=["GET"])
        def get_robot(holon_id: str):
            """Get a specific robot holon."""
            robot = self.twin.get_robot(holon_id)
            if robot:
                return jsonify(robot.to_dict())
            return jsonify({"error": f"Robot {holon_id} not found"}), 404
        
        @self.app.route("/api/operators", methods=["GET"])
        def get_operators():
            """Get all operator holons."""
            operators = self.twin.get_all_operators()
            return jsonify({
                "count": len(operators),
                "operators": [o.to_dict() for o in operators]
            })
        
        @self.app.route("/api/operators/<holon_id>", methods=["GET"])
        def get_operator(holon_id: str):
            """Get a specific operator holon."""
            operator = self.twin.get_operator(holon_id)
            if operator:
                return jsonify(operator.to_dict())
            return jsonify({"error": f"Operator {holon_id} not found"}), 404
        
        # ==================== What-If Queries ====================
        
        @self.app.route("/api/what-if/assign", methods=["POST"])
        def what_if_assign():
            """
            What-if query: simulate assigning a product to a resource.
            
            Request body:
            {
                "product_id": "dell_001",
                "resource_id": "arm_01"
            }
            """
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON body required"}), 400
            
            product_id = data.get("product_id")
            resource_id = data.get("resource_id")
            
            if not product_id or not resource_id:
                return jsonify({
                    "error": "Both product_id and resource_id required"
                }), 400
            
            result = self.twin.what_if_assign_product(product_id, resource_id)
            
            if "error" in result:
                return jsonify(result), 404
            
            return jsonify(result)
        
        @self.app.route("/api/what-if/batch-assign", methods=["POST"])
        def what_if_batch_assign():
            """
            What-if query: evaluate multiple assignment options.
            
            Request body:
            {
                "product_id": "dell_001",
                "resource_ids": ["arm_01", "arm_02", "op_01"]
            }
            """
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON body required"}), 400
            
            product_id = data.get("product_id")
            resource_ids = data.get("resource_ids", [])
            
            if not product_id or not resource_ids:
                return jsonify({
                    "error": "product_id and resource_ids required"
                }), 400
            
            results = []
            for resource_id in resource_ids:
                result = self.twin.what_if_assign_product(product_id, resource_id)
                results.append(result)
            
            # Sort by predicted success probability
            valid_results = [r for r in results if "error" not in r]
            valid_results.sort(
                key=lambda x: x.get("predicted_success_probability", 0),
                reverse=True
            )
            
            return jsonify({
                "product_id": product_id,
                "evaluated_resources": len(results),
                "results": valid_results,
                "best_option": valid_results[0] if valid_results else None,
            })
        
        # ==================== Statistics ====================
        
        @self.app.route("/api/stats", methods=["GET"])
        def get_statistics():
            """Get twin engine statistics."""
            return jsonify(self.twin.get_statistics())
        
        @self.app.route("/api/snapshot", methods=["GET"])
        def get_snapshot():
            """Get complete state snapshot."""
            return jsonify(self.twin.get_state_snapshot())
        
        @self.app.route("/api/history/<holon_id>", methods=["GET"])
        def get_history(holon_id: str):
            """Get state change history for a holon."""
            limit = request.args.get("limit", 100, type=int)
            history = self.twin.store.get_history(holon_id, limit)
            return jsonify({
                "holon_id": holon_id,
                "count": len(history),
                "history": history
            })
    
    def start(self, port: int = 5000):
        """
        Start the API server in a background thread.
        
        Args:
            port: Port to listen on
        """
        self._thread = threading.Thread(
            target=self._run_server,
            args=(port,),
            daemon=True,
            name="MediatorAPI"
        )
        self._thread.start()
        print(f"✓ Mediator API running on http://{self.host}:{port}")
    
    def _run_server(self, port: int):
        """Run the Flask server (called in background thread)."""
        # Suppress Flask's startup banner
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        self.app.run(
            host=self.host,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    
    def stop(self):
        """Stop the API server (note: Flask doesn't support graceful shutdown easily)."""
        print("✓ Mediator API stopping...")
