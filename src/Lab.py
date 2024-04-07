import threading
import numpy as np
import pandas as pd
from random import randint
from time import sleep
from matplotlib import pyplot as plt
from math import ceil
from enum import Enum
from tqdm import tqdm

from .Universe import Universe
from .Agent import Agent
from .Position import Position


class Distributions(Enum):
    random = "random"


class Lab:
    # SIMULATION
    def experiment(
        self,
        height: int,
        width: int,
        initial_population_count: int,
        max_total_duration: int,
        max_simulation_duration: int,
        verbose: bool = True,
    ) -> dict:
        assert initial_population_count <= height * width

        # Init outputs
        parameters = {
            "height": height,
            "width": width,
            "initial_population_count": initial_population_count,
            "max_total_duration": max_total_duration,
            "max_simulation_duration": max_simulation_duration,
        }
        timings = {}

        # Universe
        if verbose:
            print("Generating universe...", end="\t")
        universe = Universe(height=height, width=width)
        timings["init_universe"] = universe.get_time()
        if verbose:
            print(f": Done in {(timings['init_universe'] / 1e9):.3f} s")

        # Invoke population
        self._invoke_initial_population(
            universe, height, width, initial_population_count, verbose
        )
        assert (
            np.sum(universe.space != None) == initial_population_count
        )  # Positions are uniques
        timings["invoke_initial_population"] = universe.get_time()

        # Start population
        non_agents_threads = threading.active_count()
        self._start_initial_population(universe, verbose)
        timings["start_initial_population"] = universe.get_time()

        # Run
        early_stop = False
        start_running = universe.get_time()
        total_duration_remaining = max_total_duration - max(0, int(start_running / 1e9))
        simulation_duration = min(total_duration_remaining, max_simulation_duration)
        for i in tqdm(
            range(simulation_duration, 0, -1),
            desc="Running simulation\t",
            disable=not verbose,
            colour="yellow",
        ):
            if threading.active_count() <= non_agents_threads:
                if verbose:
                    print(f"Simulation early stop\t: All entities died.")
                early_stop = True
                break
            t = (universe.get_time() - start_running) / 1e9  # Avoiding time drift
            sleep(max(1 + simulation_duration - i - t, 0))
        timings["run"] = universe.get_time()

        # Stop
        universe.freeze.set()
        first_iteration = True
        active_agents = threading.active_count() - non_agents_threads
        while active_agents > 0:
            if first_iteration:
                print(f"Interrupting population\t: {active_agents}...")
                first_iteration = False
            else:
                print(f"\t\t\t| {active_agents}...")
            sleep(1e-1)
            active_agents = threading.active_count() - non_agents_threads
        universe.culmination = universe.get_time()
        timings["stop"] = universe.culmination

        if verbose:
            print(
                f"Simulation succeed...\t: Returning data... Done in {(timings['stop'] / 1e9):.3f} s"
            )

        return {"parameters": parameters, "timings": timings, "universe": universe}

    def _generate_position(self, positions: list[Position], height: int, width: int):
        new_pos = Position(y=randint(0, height - 1), x=randint(0, width - 1))
        if new_pos not in positions:
            return new_pos
        else:
            return self._generate_position(positions, height, width)

    def _invoke_initial_population(
        self,
        universe: Universe,
        height: int,
        width: int,
        initial_population_count: int,
        verbose: bool,
        distribution: Distributions = Distributions.random,
    ) -> None:
        positions = []
        match distribution:
            case Distributions.random:
                for _ in tqdm(
                    range(initial_population_count),
                    desc="Generating positions\t",
                    disable=not verbose,
                    colour="magenta",
                ):
                    positions.append(self._generate_position(positions, height, width))
            case _:
                raise ValueError(
                    f"Possible distributions: {[d.name for d in Distributions]}"
                )
        start_barrier = threading.Barrier(parties=initial_population_count)
        for pos in tqdm(
            positions, "Invoking population\t", disable=not verbose, colour="blue"
        ):
            Agent(
                universe=universe,
                initial_position=pos,
                generation=0,
                parents=None,
                start_barrier=start_barrier,
            )

    def _start_initial_population(self, universe, verbose: bool) -> None:
        with universe.population_lock:
            for agent in tqdm(
                universe.population.values(),
                desc="Starting population\t",
                disable=not verbose,
                colour="green",
            ):
                agent.start()

    def _stop_population(self, universe, verbose: bool) -> None:
        with universe.population_lock:  # TODO Add priority to this lock
            for agent in tqdm(
                universe.population.values(),
                desc="Stopping population\t",
                disable=not verbose,
                colour="red",
            ):
                agent.stop.set()

    # ANALYSIS
    def gather_data(self, simulation: dict, verbose: bool = True) -> dict:
        # TODO copy the universe to not alter it
        # TODO Compute med
        # Individuals statistics
        agents_statistics = []
        for a_id, agent in tqdm(
            simulation["universe"].population.items(),
            desc="Computing agents statistics\t",
            disable=not verbose,
            colour="red",
        ):
            agents_statistics.append(agent.get_data())

        agents_statistics_df = pd.DataFrame(agents_statistics)
        agents_statistics_df.set_index("id", inplace=True)

        # Population statistics
        computed_data = [
            "lifespan",
            "children_count",
            "birth_success",
            "travelled_distance",
            "actions_count",
            "mean_decision_duration",
            "mean_action_duration",
            "mean_round_duration",
        ]
        population_statistics = []
        for cp in computed_data:
            population_statistics.append(
                {
                    "data": cp,
                    "mean": agents_statistics_df[cp].mean(),
                    "median": agents_statistics_df[cp].median(),
                    "std": agents_statistics_df[cp].std(),
                }
            )
        population_statistics_df = pd.DataFrame(population_statistics)
        population_statistics_df.set_index("data", inplace=True)

        # Timelines TODO
        actions_timeline = []
        positions_timeline = []
        for a_id, agent in tqdm(
            simulation["universe"].population.items(),
            desc="Gathering timelines\t\t",
            disable=not verbose,
            colour="red",
        ):
            pass

        return {
            "agents_statistics": agents_statistics_df,
            "population_statistics": population_statistics_df,
            "actions": actions_timeline,
            "positions": positions_timeline,
        }

    # VISUALIZATION

    ##############################################################################

    def vizuaanalyze(self, n_viz=4):  # TODO Copy agents until analyse
        # TODO  Add an argument of data (agents...) to analyze or analyze last one
        n_viz = min(n_viz, Agent.count)

        # Some stats
        print(f"Total agents: {Agent.count}")
        paths_lengths = [len(agent.path) for agent in Agent.population.values()]
        paths_lengths.sort()
        path_len_mean = int(sum(paths_lengths) / len(paths_lengths))
        print(f"Agents mean path len = {path_len_mean} px")
        path_len_median = paths_lengths[len(paths_lengths) // 2]
        print(f"Agents median path len = {path_len_median} px")

        # Display paths of some agents
        agents = list([a for a in Agent.population.values()])
        fig = plt.figure()
        n_rows = ceil(n_viz ** (1 / 2))
        n_cols = ceil(n_viz / n_rows)
        for i in range(n_viz):
            plt.subplot(n_rows, n_cols, i + 1)
            plt.imshow(agents[i].array_path)
            plt.title(f"Agent's n°{agents[i].id} path")
            plt.axis("off")

    def generate_actions_timeline(self, time_step):
        # TODO maybe use copy()
        # TODO call it from analyze
        # TODO look for a method to determine optimal time_step
        actives: list = [a for a in Agent.population.values() if a.path]
        inactives: list = [a for a in Agent.population.values() if not a.path]
        time = min([a.path[0].t for a in actives])
        self.universe.init_space()  # Reset universe space

        while actives:
            # Removing deads
            actives: list = [
                a for a in actives if a.death_date is None or time < a.death_date
            ]
            inactives: list = [
                a for a in inactives if a.death_date is None or time < a.death_date
            ]
            # Update time and position of active agents

            for agent in [a for a in actives if a.path[0].t <= time]:
                i = 0
                while agent.path and agent.path[0].t <= time:
                    i += 1
                    agent.position = agent.path.pop(0)
                if i > 1:  # TODO
                    print("JUMP")
                if not agent.path:
                    actives.remove(agent)
                    inactives.append(agent)

            # Display agents
            frame = np.ones(
                (self.universe.space.shape[0], self.universe.space.shape[1], 3),
                dtype=np.uint8,
            )
            for agent in actives + inactives:
                if agent.position.t <= time:
                    frame[agent.position.y, agent.position.x] = agent.phenome.color

            time += time_step

            # Yield
            yield frame
