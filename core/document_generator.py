"""Abstract base class for document generation."""
from abc import ABC, abstractmethod
from typing import Dict, Any


class DocumentGenerator(ABC):
    """
    Abstract base class for generating documents from payment data.
    
    Subclasses should implement:
    - generate(): Create the document from JSON data
    - get_output_format(): Return the output format type
    """
    
    @abstractmethod
    def generate(self, json_data: Dict[str, Any]) -> Any:
        """
        Generate document from JSON data.
        
        Args:
            json_data: Dictionary containing payment request data
            
        Returns:
            The generated document (workbook, PDF bytes, etc.)
        """
        pass
    
    @abstractmethod
    def get_output_format(self) -> str:
        """
        Return the output format type.
        
        Returns:
            Format string: 'excel', 'pdf', etc.
        """
        pass
    
    def validate_input(self, json_data: Dict[str, Any]) -> bool:
        """
        Validate input data structure.
        
        Args:
            json_data: Input data to validate
            
        Returns:
            True if valid, raises ValueError otherwise
        """
        if not json_data:
            raise ValueError("Empty JSON data")
        if 'request' not in json_data:
            raise ValueError("Missing 'request' key in JSON data")
        return True
