"""Base class for Excel document generation with common utilities."""
from collections import defaultdict
from typing import Dict, List, Any, Tuple
import openpyxl

from core.document_generator import DocumentGenerator


class ExcelGenerator(DocumentGenerator):
    """
    Base class for Excel document generation.
    
    Provides common functionality for Excel-based reports:
    - Template loading
    - Data grouping by company and object
    - Sheet naming with length limits
    """
    
    def __init__(self, template_path: str):
        """
        Initialize the generator with a template.
        
        Args:
            template_path: Path to the Excel template file
        """
        self.template_path = template_path
        self._workbook = None
    
    def get_output_format(self) -> str:
        return 'excel'
    
    def load_template(self) -> openpyxl.Workbook:
        """Load the Excel template workbook."""
        self._workbook = openpyxl.load_workbook(self.template_path)
        return self._workbook
    
    def group_by_company_object(
        self, 
        data: List[Dict]
    ) -> Tuple[Dict[Tuple[str, str], List[Dict]], Dict[str, int]]:
        """
        Group payment data by (company, object) pairs.
        
        Args:
            data: List of payment entries
            
        Returns:
            Tuple of:
            - groups: Dict mapping (company, object) to list of entries
            - company_numbers: Dict mapping company name to numeric ID
        """
        groups = defaultdict(list)
        for item in data:
            key = (item.get('organization', ''), item.get('object_name', ''))
            groups[key].append(item)
        
        # Create company numbering
        unique_companies = sorted(set(company for company, obj in groups.keys()))
        company_numbers = {company: idx + 1 for idx, company in enumerate(unique_companies)}
        
        return dict(groups), company_numbers
    
    def create_sheet_name(
        self, 
        company_num: int, 
        object_name: str, 
        max_length: int = 31
    ) -> str:
        """
        Create a valid Excel sheet name from company number and object.
        
        Args:
            company_num: Numeric ID for the company
            object_name: Name of the object/project
            max_length: Maximum sheet name length (Excel limit is 31)
            
        Returns:
            Valid sheet name string
        """
        sheet_title = f"C{company_num}_{object_name}"
        if len(sheet_title) > max_length:
            sheet_title = sheet_title[:max_length]
        return sheet_title
    
    def save_workbook(self, filepath: str) -> None:
        """Save the workbook to a file."""
        if self._workbook:
            self._workbook.save(filepath)
    
    def close_workbook(self) -> None:
        """Close the workbook."""
        if self._workbook:
            self._workbook.close()
            self._workbook = None
