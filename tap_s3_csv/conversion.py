import singer
import pandas as pd
import numpy as np

LOGGER = singer.get_logger()

# pylint: disable=too-many-return-statements

def infer_column(column, dateFormatMap, lengths):
    if column.isnull().all():
        lengths[column.name] = 0
        return 'string'

    lengths[column.name] = column.apply(lambda x: len(str(x))).max()

    if column.dtype.name == 'object':
        # Check for list types (occurs from csv.DictReader if data row has more columns than headers)
        if column.apply(lambda x: isinstance(x, list)).any():
            return 'list'

        if infer_number(column):
            return 'number'
        elif infer_datetime(column, dateFormatMap):
            return 'date-time'
        elif infer_boolean(column):
            return 'boolean'
        else:
            return 'string'

    if column.dtype.name in ['int32', 'int64', 'float32']:
        return 'number'

def infer_number(column):
    tmpCol = column.copy()
    tmpCol = tmpCol.apply(lambda x: x.replace(',', ''))
    # empty strings are converted to NaN, which is a valid number
    # but if entire column is NaN, we want it to be inferred as string
    try:
        tmpResult = pd.to_numeric(tmpCol)
        if tmpResult.dropna().empty:
            return False
    except Exception:
        return False

    if tmpResult.dtype.name in ['float64', 'int64']:
        return True
    else:
        return False

def infer_datetime(column, dateFormatMap):
    tmpCol = column.copy()
    # SalesForce exports empty dates as <NULL>
    tmpCol.replace('(?i)<null>', '', inplace=True, regex=True)
    # if entire column is empty string, we want it to be inferred as string
    tmpCol = tmpCol.replace('', np.nan).dropna()
    if tmpCol.empty:
        return False
    # pandas does not check the format properly
    return infer_datetime_and_format(tmpCol, dateFormatMap)


def infer_datetime_and_format(column, dateFormatMap):
    column = column[column.astype(bool)] # Ignore empty strings/blank rows - they fail parsing for all but the first format

    try:
        # Formats '%Y-%m-%d' and '%Y/%m/%d' seem work interchangeably in pd.to_datetime function
        # e.g '2022-01-02' and '2022/01/02' would both pass pd.to_datetime using formats '%Y-%m-%d'
        # and '%Y/%m/%d'
        # Choose one cell to check if '/' is in the value and update dateFormatMap correctly
        cell = column.min()
        column = pd.to_datetime(column, format='%Y-%m-%d')
        dateFormatMap[column.name] = 'YYYY/MM/DD' if '/' in cell else 'YYYY-MM-DD'
        return True
    except Exception as e:
        pass

    try:
        column = pd.to_datetime(column, format='%m-%d-%Y')
        dateFormatMap[column.name] = 'MM-DD-YYYY'
        return False
    except Exception as e:
        pass

    try:
        column = pd.to_datetime(column, format='%d-%m-%Y')
        dateFormatMap[column.name] = 'DD-MM-YYYY'
        return False
    except Exception as e:
        pass

    try:
        column = pd.to_datetime(column, format='%m/%d/%Y')
        dateFormatMap[column.name] = 'MM/DD/YYYY'
        return False
    except Exception as e:
        pass

    try:
        column = pd.to_datetime(column, format='%d/%m/%Y')
        dateFormatMap[column.name] = 'DD/MM/YYYY'
        return False
    except Exception as e:
        pass

    return False


def infer_boolean(column):
    column = column.replace('', np.nan) # Replace empty strings with NaN so they are properly handled
    unique_values = column.unique()

    if len(unique_values) == 0:
        return False

    # If there's only one value and it's blank/missing, then it's not a boolean column
    if len(unique_values) == 1 and pd.isna(unique_values[0]):
        return False

    # All values must be boolean or blank/missing
    for value in unique_values:
        if not is_boolean_value(value) and not pd.isna(value):
            return False

    return True


def is_boolean_value(value):
    if isinstance(value, str) and (value.lower() == 'true' or value.lower() == 'false'):
        return True

    if value is True or value is np.True_:
        return True

    if value is False or value is np.False_:
        return True

    return False


def generate_schema(samples, table_spec, string_max_length: bool):
    df = pd.DataFrame(samples)
    col_types = {}
    date_format_map = {} # Stores date formats for any columns that can be interpretted as dates
    lengths = {} # Stores the maximum length of strings in each column
    for col_name in df.columns:
        col_types[col_name] = infer_column(df[col_name], date_format_map, lengths)

    schema = {}
    for col_name, datatype in col_types.items():
        # Ignore list datatypes (autogenerated if rows have more columns than header row)
        if datatype != 'list':
            schema[col_name] = datatype_schema(datatype, lengths[col_name], string_max_length)

    return schema, date_format_map


def datatype_schema(datatype, length, string_max_length: bool):
    if datatype == 'date-time':
        schema = {'type': ['null', 'string'], 'format': 'date-time'}
        if string_max_length:
            schema['maxLength'] = length
    elif datatype == 'dict':
        schema = {
            'anyOf': [
                {'type': 'object', 'properties': {}},
                {'type': ['null', 'string']}
            ]
        }
        if string_max_length:
            schema['anyOf'][1]['maxLength'] = length
    else:
        types = ['null', datatype]
        if datatype != 'string':
            types.append('string')
        schema = {
            'type': types,
        }
        if string_max_length:
            schema['maxLength'] = length
    return schema
