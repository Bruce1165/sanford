#!/usr/bin/env python3
"""
Input Validation Module
Validates API request inputs to prevent invalid data
"""
import re
from datetime import datetime
from typing import Tuple, Optional, Any, Dict


class ValidationError(Exception):
    """Custom validation error"""
    pass


def validate_screener_name(name: str) -> Tuple[bool, str]:
    """
    Validate screener name
    Returns: (is_valid, error_message)
    """
    if not name:
        return False, "Screener name is required"
    if len(name) > 50:
        return False, "Screener name too long (max 50 characters)"
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        return False, "Screener name can only contain letters, numbers, and underscores"
    return True, ""


def validate_date(date_str: str) -> Tuple[bool, str]:
    """
    Validate date format (YYYY-MM-DD)
    Returns: (is_valid, error_message)
    """
    if not date_str:
        return False, "Date is required"
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        # Check reasonable range (not in future, not too old)
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now()
        if dt > today:
            return False, "Date cannot be in the future"
        if dt.year < 2020:
            return False, "Date too old (must be after 2020-01-01)"
        return True, ""
    except ValueError:
        return False, "Invalid date format, use YYYY-MM-DD"


def validate_stock_code(code: str) -> Tuple[bool, str]:
    """
    Validate stock code (6 digits)
    Returns: (is_valid, error_message)
    """
    if not code:
        return False, "Stock code is required"
    if not re.match(r'^\d{6}$', code):
        return False, "Stock code must be 6 digits"
    return True, ""


def validate_page_params(page: int, page_size: int, max_page_size: int = 100) -> Tuple[bool, str]:
    """
    Validate pagination parameters
    Returns: (is_valid, error_message)
    """
    if page < 1:
        return False, "Page number must be >= 1"
    if page_size < 1:
        return False, "Page size must be >= 1"
    if page_size > max_page_size:
        return False, f"Page size too large (max {max_page_size})"
    return True, ""


def validate_screener_run_request(data: dict) -> Tuple[bool, str, dict]:
    """
    Validate screener run request
    Returns: (is_valid, error_message, validated_data)
    """
    # Validate date
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    is_valid, error = validate_date(date_str)
    if not is_valid:
        return False, f"Invalid date: {error}", {}

    # Validate screener name if provided
    if 'screener_name' in data:
        is_valid, error = validate_screener_name(data['screener_name'])
        if not is_valid:
            return False, f"Invalid screener name: {error}", {}

    return True, "", {'date': date_str}


def validate_upload_request(file_obj, force_update: str) -> Tuple[bool, str, dict]:
    """
    Validate file upload request
    Returns: (is_valid, error_message, validated_data)
    """
    # Check file exists
    if not file_obj or file_obj.filename == '':
        return False, "No file uploaded", {}

    # Check file extension
    if not file_obj.filename.lower().endswith(('.xls', '.xlsx')):
        return False, "Invalid file type, only .xls or .xlsx allowed", {}

    # Validate force_update parameter
    force_update_bool = force_update.lower() == 'true'

    return True, "", {'force_update': force_update_bool}


def sanitize_string(input_str: str, max_length: int = 255) -> str:
    """
    Sanitize string input
    Returns: sanitized string
    """
    if not input_str:
        return ""
    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', str(input_str))
    # Truncate to max length
    return sanitized[:max_length].strip()


def validate_request(data: dict, schema: dict) -> Tuple[bool, str, dict]:
    """
    Generic request validator based on schema
    Schema format: {'field_name': {'type': type, 'required': bool, 'max_length': int}}
    Returns: (is_valid, error_message, validated_data)
    """
    validated = {}
    errors = []

    for field, rules in schema.items():
        field_name = rules.get('name', field)
        is_required = rules.get('required', False)
        field_type = rules.get('type', str)
        max_length = rules.get('max_length', None)

        value = data.get(field)

        # Check required
        if is_required and value is None:
            errors.append(f"{field_name} is required")
            continue

        # Skip optional fields if not provided
        if not is_required and value is None:
            continue

        # Type validation
        try:
            if field_type == int:
                value = int(value)
            elif field_type == float:
                value = float(value)
            elif field_type == bool:
                value = str(value).lower() in ('true', '1', 'yes')
            elif field_type == str:
                value = sanitize_string(str(value), max_length or 255)
        except (ValueError, TypeError):
            errors.append(f"{field_name} must be {field_type.__name__}")
            continue

        validated[field] = value

    if errors:
        return False, "; ".join(errors), {}

    return True, "", validated


# ========== Screener Config Validation ==========

def validate_screener_config(config: Dict, schema: Dict) -> Tuple[bool, Dict[str, str]]:
    """
    Validate screener configuration

    Args:
        config: 配置字典
        schema: 参数Schema

    Returns:
        (是否有效, 错误字典)
    """
    errors = {}

    # 验证参数
    if 'parameters' in config:
        from config_loader import ConfigLoader
        all_valid, param_errors = ConfigLoader.validate_parameters(
            config['parameters'],
            schema
        )
        if not all_valid:
            errors.update(param_errors)

    # 验证必填字段
    if not config.get('display_name'):
        errors['display_name'] = 'Display name is required'

    return len(errors) == 0, errors

def validate_screener_config_update(data: Dict) -> Tuple[bool, str, Dict]:
    """
    Validate screener config update request

    Returns:
        (是否有效, 错误信息, 验证后的数据)
    """
    validated = {}

    # 验证必填字段
    if 'parameters' not in data:
        return False, "Parameters are required", {}

    if 'change_summary' not in data or not data['change_summary'].strip():
        return False, "Change summary is required", {}

    if 'updated_by' not in data:
        data['updated_by'] = 'system'

    validated['change_summary'] = data['change_summary'].strip()
    validated['updated_by'] = data['updated_by']

    # 可选字段
    if 'display_name' in data:
        if not data['display_name'].strip():
            return False, "Display name cannot be empty"
        validated['display_name'] = data['display_name'].strip()

    if 'description' in data:
        validated['description'] = data['description'].strip()

    if 'category' in data:
        validated['category'] = data['category'].strip()

    validated['parameters'] = data['parameters']

    return True, "", validated

