from __future__ import annotations

import inspect


def build_parse_request_form_data_compat(
    api_client,
    *,
    language: str,
    backend: str,
    formula: bool,
    table: bool,
    start_page: int,
    end_page: int | None,
    server_url: str | None,
):
    kwargs = dict(
        lang_list=[language],
        backend=backend,
        parse_method="auto",
        formula_enable=formula,
        table_enable=table,
        start_page_id=start_page,
        end_page_id=end_page,
        return_md=True,
        return_content_list=True,
        return_middle_json=True,
        return_model_output=False,
        return_images=True,
        response_format_zip=True,
        return_original_file=False,
    )
    signature = inspect.signature(api_client.build_parse_request_form_data)
    if "server_url" in signature.parameters:
        kwargs["server_url"] = server_url
    return api_client.build_parse_request_form_data(**kwargs)
