"""Local frontend bridge for RubberDucky.

The bridge is a thin, read-mostly adapter over the existing Python pipeline.
It never reimplements STT, triage, Git collection, LLM analysis or TTS.
"""
