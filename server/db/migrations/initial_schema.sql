-- CloudAIoT 최초 스키마 (PostgreSQL)
-- server/db/models.py에서 생성했다. 직접 고치지 말고 `python -m server.db.models`로 다시 만든다.
-- 시간 컬럼(*_ms)은 UTC Unix 밀리초다.

CREATE TABLE gesture_mappings (
	gesture VARCHAR(16) NOT NULL,
	action VARCHAR(8) NOT NULL,
	enabled BOOLEAN NOT NULL,
	updated_at_ms BIGINT NOT NULL,
	PRIMARY KEY (gesture)
);

CREATE TABLE users (
	user_id VARCHAR(64) NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	name VARCHAR(100) NOT NULL,
	role VARCHAR(16) NOT NULL,
	created_at_ms BIGINT NOT NULL,
	PRIMARY KEY (user_id),
	UNIQUE (email)
);

CREATE TABLE guardian_links (
	guardian_id VARCHAR(64) NOT NULL,
	user_id VARCHAR(64) NOT NULL,
	created_at_ms BIGINT NOT NULL,
	PRIMARY KEY (guardian_id, user_id),
	FOREIGN KEY(guardian_id) REFERENCES users (user_id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE help_requests (
	request_id VARCHAR(64) NOT NULL,
	correlation_id VARCHAR(64) NOT NULL,
	user_id VARCHAR(64) NOT NULL,
	source VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_at_ms BIGINT NOT NULL,
	confirmed_at_ms BIGINT,
	confirmed_by VARCHAR(64),
	completed_at_ms BIGINT,
	completed_by VARCHAR(64),
	PRIMARY KEY (request_id),
	FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE,
	FOREIGN KEY(confirmed_by) REFERENCES users (user_id) ON DELETE SET NULL,
	FOREIGN KEY(completed_by) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE INDEX ix_help_requests_correlation_id ON help_requests (correlation_id);

CREATE INDEX ix_help_requests_created ON help_requests (created_at_ms);

CREATE INDEX ix_help_requests_status ON help_requests (status);

CREATE INDEX ix_help_requests_user_id ON help_requests (user_id);

CREATE TABLE rooms (
	room_id VARCHAR(64) NOT NULL,
	name VARCHAR(100) NOT NULL,
	description VARCHAR(500),
	resident_user_id VARCHAR(64),
	created_at_ms BIGINT NOT NULL,
	updated_at_ms BIGINT NOT NULL,
	PRIMARY KEY (room_id),
	FOREIGN KEY(resident_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE TABLE devices (
	device_id VARCHAR(64) NOT NULL,
	room_id VARCHAR(64) NOT NULL,
	name VARCHAR(100) NOT NULL,
	device_type VARCHAR(32) NOT NULL,
	map_x FLOAT NOT NULL,
	map_y FLOAT NOT NULL,
	min_angle_deg FLOAT NOT NULL,
	max_angle_deg FLOAT NOT NULL,
	enabled BOOLEAN NOT NULL,
	state VARCHAR(16) NOT NULL,
	connection_status VARCHAR(16) NOT NULL,
	state_updated_at_ms BIGINT,
	created_at_ms BIGINT NOT NULL,
	updated_at_ms BIGINT NOT NULL,
	PRIMARY KEY (device_id),
	FOREIGN KEY(room_id) REFERENCES rooms (room_id) ON DELETE RESTRICT
);

CREATE INDEX ix_devices_room_id ON devices (room_id);

CREATE TABLE control_events (
	command_id VARCHAR(64) NOT NULL,
	correlation_id VARCHAR(64) NOT NULL,
	device_id VARCHAR(64) NOT NULL,
	action VARCHAR(8) NOT NULL,
	source VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	result VARCHAR(16),
	error_code VARCHAR(64),
	gesture_confirmed_at_ms BIGINT,
	command_published_at_ms BIGINT NOT NULL,
	ack_received_at_ms BIGINT,
	latency_ms BIGINT,
	PRIMARY KEY (command_id),
	FOREIGN KEY(device_id) REFERENCES devices (device_id) ON DELETE CASCADE
);

CREATE INDEX ix_control_events_correlation_id ON control_events (correlation_id);

CREATE INDEX ix_control_events_device_id ON control_events (device_id);

CREATE INDEX ix_control_events_published ON control_events (command_published_at_ms);
