build:
	docker build --no-cache . --network=host -t oraluben/tidb-poc

push: build
	docker push oraluben/tidb-poc

.PHONY: build