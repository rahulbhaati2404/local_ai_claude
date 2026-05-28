class TokenCounter:

    def estimate_tokens(
        self,
        text: str
    ) -> int:

        # rough approximation
        return int(len(text.split()) * 1.3)


token_counter = TokenCounter()