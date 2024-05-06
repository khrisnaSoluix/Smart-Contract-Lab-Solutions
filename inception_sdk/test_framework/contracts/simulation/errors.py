def generic_error(message: str):
    return ValueError(
        {
            "grpc_code": 3,
            "http_code": 400,
            "message": message,
            "http_status": "Bad Request",
        }
    )


def missing_parameter(missing_param: str):
    message = (
        f"value was not provided for non-derived, "
        f'non-optional instance parameter with name "{missing_param}"'
    )
    return generic_error(message=message)


def param_not_exist(param: str, reason_suffix: str | None = ""):
    message = f'non-derived instance parameter with name "{param}" does not exist{reason_suffix}'
    return generic_error(message=message)
