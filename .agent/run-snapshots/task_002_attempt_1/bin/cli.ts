#!/usr/bin/env node
/** Responsibility: process entrypoint that boots the compiled CLI program. */
import { runCli } from "../src/index.js";

void runCli(process.argv);
