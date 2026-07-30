class BioCoreClientError(RuntimeError):
    pass


class BioCoreAuthRequired(BioCoreClientError):
    def __init__(self, authorize_url: str) -> None:
        super().__init__("Central BioCore authentication is required")
        self.authorize_url = authorize_url


class BioCoreAccessDenied(BioCoreClientError):
    pass


class BioCoreUnavailable(BioCoreClientError):
    pass
