/**
 * Mózg sesji omp w terminalu właściciela (docs/WIEDZA.md §4c, jarvo/mozg_sesji.py).
 *
 * Skrzynka (jarvo/sesje_omp.py) dokleja przypomnienie do wiadomości tury sama; terminal to interaktywny omp, więc
 * tę samą robotę robi ta wtyczka. Ładuje ją `jarvo sesja <klucz> terminal` (`omp -e <ten plik>`) tylko dla wpisu
 * z `panel.wiedza` i ustawia JARVO_SESJA_WIEDZA: lista JSON z poleceniem `… jarvo sesja <klucz> wiedza` (ten sam
 * Python i kod co terminal). Bez tej zmiennej wtyczka nic nie robi.
 *
 * - before_agent_start: `… wiedza przed-tura` (tekst właściciela na stdin; wiadomość w trakcie biegu z `--dopisek`,
 *   jak dopisek skrzynki: bez zapisu do rejestru). Stdout = blok `<memory-context>` jako ukryta wiadomość
 *   (`display: false`: idzie do kontekstu i do pliku sesji, terminal jej nie rysuje); na pasku stanu krótko
 *   „pamięć: notatki N, linki M”. Limit LIMIT_MS, błąd albo przekroczony czas = tura bez bloku, nigdy blokada.
 * - agent_end: `… wiedza po-turze` w tle (JSON z tekstami właściciela tej tury i ostatnią odpowiedzią na stdin
 *   z pliku tymczasowego), proces odłączony: następny prompt na niego nie czeka.
 * Podagenci (task, /tan) i wznowienia podagenta mózgu nie wołają.
 */
import { type ChildProcess, spawn } from "node:child_process";
import { closeSync, mkdtempSync, openSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const LIMIT_MS = 6000; // przypomnienie Kernela do 3,6 s (dziennik 22.11) + start Pythona
const TYP = "jarvo-pamiec";

interface Przypomnienie {
	blok: string;
	blad?: string;
}

function polecenie(): string[] | null {
	const surowe = process.env.JARVO_SESJA_WIEDZA;
	if (!surowe) return null;
	try {
		const p: unknown = JSON.parse(surowe);
		return Array.isArray(p) && p.length > 0 && p.every(a => typeof a === "string") ? p : null;
	} catch {
		return null;
	}
}

function przedTura(cmd: string[], tekst: string, dopisek: boolean): Promise<Przypomnienie> {
	const { promise, resolve } = Promise.withResolvers<Przypomnienie>();
	let dziecko: ChildProcess;
	try {
		dziecko = spawn(cmd[0], [...cmd.slice(1), "przed-tura", ...(dopisek ? ["--dopisek"] : [])], {
			stdio: ["pipe", "pipe", "ignore"],
			detached: true,
		});
	} catch (e) {
		return Promise.resolve({ blok: "", blad: String(e).slice(0, 80) });
	}
	let out = "";
	let koniec = false;
	const zegar = setTimeout(() => {
		try {
			if (dziecko.pid) process.kill(-dziecko.pid, "SIGKILL"); // grupa: Python i ranking bazy (kb)
		} catch {
			// już skończył
		}
		zakoncz({ blok: "", blad: `ponad ${LIMIT_MS / 1000} s` });
	}, LIMIT_MS);
	const zakoncz = (w: Przypomnienie) => {
		if (koniec) return;
		koniec = true;
		clearTimeout(zegar);
		resolve(w);
	};
	dziecko.stdout?.setEncoding("utf8");
	dziecko.stdout?.on("data", (d: string) => {
		out += d;
	});
	dziecko.on("error", e => zakoncz({ blok: "", blad: String(e).slice(0, 80) }));
	dziecko.on("close", kod => zakoncz(kod === 0 ? { blok: out.trim() } : { blok: "", blad: `kod ${kod}` }));
	dziecko.stdin?.on("error", () => {});
	dziecko.stdin?.end(tekst);
	return promise;
}

function poTurze(cmd: string[], wiadomosci: string[], odpowiedz: string): void {
	let katalog = "";
	try {
		katalog = mkdtempSync(join(tmpdir(), "jarvo-po-turze-"));
		const plik = join(katalog, "tura.json");
		writeFileSync(plik, JSON.stringify({ wiadomosci, odpowiedz }));
		const fd = openSync(plik, "r");
		try {
			const dziecko = spawn(cmd[0], [...cmd.slice(1), "po-turze"], {
				stdio: [fd, "ignore", "ignore"],
				detached: true,
			});
			dziecko.on("error", () => {});
			dziecko.unref();
		} finally {
			closeSync(fd); // dziecko ma własną kopię deskryptora: plik może zniknąć
		}
	} catch {
		// po turze to tylko porządki w bazie: błąd nie może dotknąć terminala
	} finally {
		if (katalog) rmSync(katalog, { recursive: true, force: true });
	}
}

/** Tekst ostatniej odpowiedzi modelu w biegu (bloki `text` asystenta). */
function tekstOdpowiedzi(wiadomosci: readonly unknown[]): string {
	for (let i = wiadomosci.length - 1; i >= 0; i--) {
		const m = wiadomosci[i];
		if (!m || typeof m !== "object" || !("role" in m) || m.role !== "assistant" || !("content" in m)) continue;
		if (!Array.isArray(m.content)) continue;
		const t = m.content
			.map((c: unknown) =>
				c && typeof c === "object" && "type" in c && c.type === "text" && "text" in c && typeof c.text === "string"
					? c.text
					: "",
			)
			.join("")
			.trim();
		if (t) return t;
	}
	return "";
}

export default function mozgSesji(pi: ExtensionAPI) {
	const cmd = polecenie();
	if (!cmd) return;
	let biegnie = false;
	let teksty: string[] = [];
	const glowny = (ctx: { agent?: { kind: string } }) => (ctx.agent?.kind ?? "main") === "main";

	pi.on("before_agent_start", async (event, ctx) => {
		if (event.reason !== "prompt" || !glowny(ctx)) return;
		const prompt = String(event.prompt ?? "");
		if (prompt.trim() && teksty[teksty.length - 1] !== prompt) teksty.push(prompt);
		const w = await przedTura(cmd, prompt, biegnie);
		const notatki = (w.blok.match(/^- `[^`]+` · /gm) ?? []).length;
		const linki = (w.blok.match(/^- https?:\/\//gm) ?? []).length;
		try {
			if (ctx.hasUI)
				ctx.ui.setStatus(
					TYP,
					w.blad
						? `pamięć: bez bloku (${w.blad})`
						: w.blok
							? `pamięć: notatki ${notatki}, linki ${linki}`
							: "pamięć: nic do przypomnienia",
				);
		} catch {
			// pasek stanu to tylko podpowiedź
		}
		if (!w.blok) return;
		return { message: { customType: TYP, content: w.blok, display: false } };
	});

	pi.on("agent_start", async (_event, ctx) => {
		if (glowny(ctx)) biegnie = true;
	});

	pi.on("agent_end", async (event, ctx) => {
		if (!glowny(ctx)) return;
		biegnie = false;
		const tury = teksty;
		teksty = [];
		if (tury.length) poTurze(cmd, tury, tekstOdpowiedzi(event.messages ?? []));
	});
}
