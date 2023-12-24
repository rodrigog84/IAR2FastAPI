ALTER TABLE `iar2_empresas`
	ADD COLUMN `greeting` TEXT NULL DEFAULT NULL AFTER `promp1`,
	ADD COLUMN `whatsapp` TINYINT NULL DEFAULT '0' AFTER `closeminutes`,
	ADD COLUMN `webchat` TINYINT NULL DEFAULT '0' AFTER `whatsapp`,
	ADD COLUMN `derivacion` TINYINT NULL DEFAULT '0' AFTER `webchat`,
	ADD COLUMN `crm` TINYINT NULL DEFAULT '0' AFTER `derivacion`;



CREATE TABLE `iar2_interaction` (
	`id` INT(11) NOT NULL AUTO_INCREMENT,
	`identerprise` INT(11) NOT NULL DEFAULT '0',
	`typemessage` VARCHAR(50) NOT NULL COLLATE 'utf8mb4_general_ci',
	`valuetype` VARCHAR(100) NOT NULL COLLATE 'utf8mb4_general_ci',
	`lastmessage` TEXT NOT NULL COLLATE 'utf8mb4_general_ci',
	`lastmessageresponsecustomer` TEXT NOT NULL COLLATE 'utf8mb4_general_ci',
	`lastyperesponse` VARCHAR(50) NOT NULL DEFAULT '' COLLATE 'utf8mb4_general_ci',
	`derivation` TINYINT(4) NOT NULL DEFAULT '0',
	`finish` TINYINT(4) NOT NULL DEFAULT '0',
	`updated_at` DATETIME NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
	PRIMARY KEY (`id`) USING BTREE
)
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;


ALTER TABLE `iar2_empresas`
	CHANGE COLUMN `derivacion` `derivation` TINYINT(4) NULL DEFAULT '0' AFTER `webchat`,
	ADD COLUMN `time_min` TIME NULL AFTER `crm`,
	ADD COLUMN `time_max` TIME NULL AFTER `time_min`;

ALTER TABLE `iar2_empresas`
	ADD COLUMN `chatbot` TINYINT(4) NULL DEFAULT '0' AFTER `webchat`;


ALTER TABLE `iar2_interaction`
	CHANGE COLUMN `lastmessage` `lastmessage` TEXT NULL COLLATE 'utf8mb4_general_ci' AFTER `valuetype`,
	CHANGE COLUMN `lastmessageresponsecustomer` `lastmessageresponsecustomer` TEXT NULL COLLATE 'utf8mb4_general_ci' AFTER `lastmessage`,
	CHANGE COLUMN `lastyperesponse` `lastyperesponse` VARCHAR(50) NOT NULL DEFAULT '' COLLATE 'utf8mb4_general_ci' AFTER `lastmessageresponsecustomer`;

ALTER TABLE `iar2_empresas`
	ADD COLUMN `derivation_message` TEXT NULL DEFAULT NULL AFTER `greeting`;


ALTER TABLE `iar2_captura`
	CHANGE COLUMN `message` `message` TEXT NOT NULL COLLATE 'utf8mb4_general_ci' AFTER `valuetype`,
	CHANGE COLUMN `messageresponseia` `messageresponseia` TEXT NULL COLLATE 'utf8mb4_general_ci' AFTER `message`,
	CHANGE COLUMN `messageresponsecustomer` `messageresponsecustomer` TEXT NOT NULL COLLATE 'utf8mb4_general_ci' AFTER `messageresponseia`;                

ALTER TABLE `iar2_interaction`
	ADD COLUMN `alert_finish` TINYINT(4) NOT NULL DEFAULT '0' AFTER `derivation`;    