"""
Algorithm registry for plugin-based detection algorithm registration.

Enables algorithms to be registered and retrieved by name, supporting
a plugin-based architecture where new algorithms can be added without
modifying core code.
"""

from __future__ import annotations

from typing import Dict, List, Type, TypeVar

from .base import DetectionAlgorithm

# Type variable for algorithm classes
T = TypeVar("T", bound=DetectionAlgorithm)


class AlgorithmRegistry:
    """
    Registry for detection algorithms.
    
    Provides a decorator-based registration system where algorithms
    can be registered and retrieved by name. Supports filtering by
    enabled algorithm names.
    
    Example:
        >>> @AlgorithmRegistry.register
        ... class MyAlgorithm(DetectionAlgorithm):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_algorithm"
        ...     
        ...     @property
        ...     def description(self) -> str:
        ...         return "My algorithm"
        ...     
        ...     def detect(self, events):
        ...         return []
        >>> 
        >>> # Retrieve algorithm
        >>> algorithm = AlgorithmRegistry.get("my_algorithm")
        >>> algorithm.name
        'my_algorithm'
        >>> 
        >>> # List all algorithms
        >>> AlgorithmRegistry.list_all()
        ['my_algorithm']
        >>> 
        >>> # Get all algorithms (optionally filtered)
        >>> algorithms = AlgorithmRegistry.get_all()
        >>> algorithms = AlgorithmRegistry.get_all(enabled=["my_algorithm"])
    """
    
    # Class-level registry storage
    _algorithms: Dict[str, Type[DetectionAlgorithm]] = {}
    
    @classmethod
    def register(cls, algorithm_class: Type[T]) -> Type[T]:
        """
        Decorator to register a detection algorithm class.
        
        Registers the algorithm class by its name property. The algorithm
        must implement the DetectionAlgorithm interface and have a unique name.
        
        Args:
            algorithm_class: Class that inherits from DetectionAlgorithm.
                Must implement `name` property that returns a unique string.
        
        Returns:
            The same algorithm class (for use as decorator).
        
        Raises:
            ValueError: If algorithm name is already registered.
            ValueError: If algorithm class doesn't implement DetectionAlgorithm.
            ValueError: If algorithm name is empty or invalid.
        
        Example:
            >>> @AlgorithmRegistry.register
            ... class MyAlgorithm(DetectionAlgorithm):
            ...     @property
            ...     def name(self) -> str:
            ...         return "my_algorithm"
            ...     # ... other required methods ...
        """
        # Validate that class implements DetectionAlgorithm
        if not issubclass(algorithm_class, DetectionAlgorithm):
            raise ValueError(
                f"Algorithm class {algorithm_class.__name__} must inherit from DetectionAlgorithm"
            )
        
        # Create temporary instance to get name (for validation)
        # This ensures name property is implemented correctly
        try:
            temp_instance = algorithm_class()
            algorithm_name = temp_instance.name
        except Exception as e:
            raise ValueError(
                f"Cannot instantiate algorithm class {algorithm_class.__name__}: {e}"
            ) from e
        
        # Validate algorithm name
        if not algorithm_name or not isinstance(algorithm_name, str):
            raise ValueError(
                f"Algorithm {algorithm_class.__name__} must have a non-empty string name property"
            )
        
        # Check for duplicate registration
        if algorithm_name in cls._algorithms:
            existing_class = cls._algorithms[algorithm_name]
            raise ValueError(
                f"Algorithm name '{algorithm_name}' is already registered by {existing_class.__name__}. "
                f"Cannot register {algorithm_class.__name__} with the same name."
            )
        
        # Register the algorithm
        cls._algorithms[algorithm_name] = algorithm_class
        
        return algorithm_class
    
    @classmethod
    def get(cls, name: str) -> DetectionAlgorithm:
        """
        Retrieve a registered algorithm by name.
        
        Creates and returns a new instance of the algorithm class.
        Each call returns a fresh instance (algorithms are stateless).
        
        Args:
            name: Algorithm name (as returned by algorithm.name property).
        
        Returns:
            Instance of the registered algorithm.
        
        Raises:
            KeyError: If algorithm name is not registered.
        
        Example:
            >>> algorithm = AlgorithmRegistry.get("layering")
            >>> isinstance(algorithm, DetectionAlgorithm)
            True
        """
        if name not in cls._algorithms:
            available = ", ".join(sorted(cls._algorithms.keys()))
            raise KeyError(
                f"Algorithm '{name}' is not registered. "
                f"Available algorithms: {available if available else '(none)'}"
            )
        
        algorithm_class = cls._algorithms[name]
        return algorithm_class()
    
    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all registered algorithm names.
        
        Returns:
            List of algorithm names, sorted alphabetically.
        
        Example:
            >>> AlgorithmRegistry.list_all()
            ['layering', 'wash_trading']
        """
        return sorted(cls._algorithms.keys())
    
    @classmethod
    def get_all(cls, enabled: List[str] | None = None) -> List[DetectionAlgorithm]:
        """
        Get all registered algorithms, optionally filtered by enabled list.
        
        If enabled list is provided, only returns algorithms whose names
        are in the enabled list. If enabled list is None, returns all
        registered algorithms.
        
        Args:
            enabled: Optional list of algorithm names to include.
                If None, returns all registered algorithms.
                If provided, only returns algorithms with names in this list.
        
        Returns:
            List of algorithm instances, sorted by name.
            Empty list if enabled list is provided but empty.
        
        Raises:
            KeyError: If enabled list contains an unregistered algorithm name.
        
        Example:
            >>> # Get all algorithms
            >>> all_algorithms = AlgorithmRegistry.get_all()
            >>> 
            >>> # Get only enabled algorithms
            >>> enabled = AlgorithmRegistry.get_all(enabled=["layering", "wash_trading"])
            >>> 
            >>> # Empty list if enabled is empty
            >>> empty = AlgorithmRegistry.get_all(enabled=[])
            >>> len(empty)
            0
        """
        if enabled is None:
            # Return all registered algorithms
            return [cls.get(name) for name in cls.list_all()]
        
        # Validate all enabled names are registered
        available_names = set(cls._algorithms.keys())
        invalid_names = set(enabled) - available_names
        
        if invalid_names:
            available = ", ".join(sorted(available_names))
            raise KeyError(
                f"Enabled list contains unregistered algorithms: {sorted(invalid_names)}. "
                f"Available algorithms: {available if available else '(none)'}"
            )
        
        # Return enabled algorithms, sorted by name
        return [cls.get(name) for name in sorted(enabled)]
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered algorithms (for testing purposes only).
        
        WARNING: This method should only be used in tests to reset
        the registry state. Do not use in production code.
        """
        cls._algorithms.clear()

