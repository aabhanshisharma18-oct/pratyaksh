.PHONY: web build test demo d2-test d2-samples
web:
	npm run dev
build:
	npm run build
test:
	npm test
demo:
	python -m backend.d2.demo
d2-test:
	python -m pytest backend/d2/tests -q
d2-samples:
	python -m backend.d2.samples.generate
