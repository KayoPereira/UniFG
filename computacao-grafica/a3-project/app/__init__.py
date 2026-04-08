from __future__ import annotations


def create_app():
	from .web import create_app as build_app

	return build_app()


__all__ = ["create_app"]
