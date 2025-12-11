"""Google Gemini LLM client."""

from typing import Any, Optional

import google.generativeai as genai
import structlog

from research_agent.config import LLMConfig

logger = structlog.get_logger()


class GeminiClient:
    """Client for Google Gemini API."""

    def __init__(self, config: LLMConfig) -> None:
        """Initialize Gemini client.
        
        Args:
            config: LLM configuration
        """
        self.config = config
        
        if not config.gemini_api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=config.gemini_api_key.get_secret_value())
        
        self.model = genai.GenerativeModel(
            model_name=config.gemini_model,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
            },
        )
        
        logger.info(
            "gemini_client_initialized",
            model=config.gemini_model,
            temperature=config.temperature,
        )

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using Gemini.
        
        Args:
            prompt: User prompt
            system_instruction: Optional system instruction
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        try:
            # If system instruction is provided, create a new model instance
            if system_instruction:
                model = genai.GenerativeModel(
                    model_name=self.config.gemini_model,
                    generation_config={
                        "temperature": kwargs.get("temperature", self.config.temperature),
                        "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                    },
                    system_instruction=system_instruction,
                )
            else:
                model = self.model
            
            response = await model.generate_content_async(prompt)
            
            if not response.text:
                logger.error("empty_response_from_gemini")
                raise ValueError("Empty response from Gemini")
            
            logger.info(
                "gemini_generation_complete",
                prompt_length=len(prompt),
                response_length=len(response.text),
            )
            
            return response.text
            
        except Exception as e:
            logger.error("gemini_generation_error", error=str(e))
            raise

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate structured output using Gemini.
        
        Args:
            prompt: User prompt
            system_instruction: Optional system instruction
            response_schema: Optional JSON schema for structured output
            **kwargs: Additional generation parameters
            
        Returns:
            Structured response as dictionary
        """
        import json
        
        try:
            # Add instruction for JSON output
            json_prompt = f"""{prompt}

Please provide your response in valid JSON format."""
            
            if response_schema:
                json_prompt += f"\n\nThe response should follow this schema:\n{json.dumps(response_schema, indent=2)}"
            
            response_text = await self.generate(
                prompt=json_prompt,
                system_instruction=system_instruction,
                **kwargs,
            )
            
            # Extract JSON from response (handle markdown code blocks)
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            logger.info("gemini_structured_generation_complete")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("json_decode_error", error=str(e), response=response_text[:500])
            raise
        except Exception as e:
            logger.error("gemini_structured_generation_error", error=str(e))
            raise
